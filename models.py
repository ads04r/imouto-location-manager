from django.db import models
import datetime, pytz, math

class Position(models.Model):
    lat = models.FloatField()
    lon = models.FloatField()
    elevation = models.FloatField(null=True, blank=True)
    time = models.DateTimeField(unique=True)
    speed = models.IntegerField(blank=True, null=True)
    explicit = models.BooleanField(default=True)
    source = models.SlugField(max_length=32)
    class Meta:
        app_label = 'locman'
        verbose_name = 'position'
        verbose_name_plural = 'positions'
        indexes = [
            models.Index(fields=['lat', 'lon']),
            models.Index(fields=['speed']),
            models.Index(fields=['explicit']),
            models.Index(fields=['source']),
            models.Index(fields=['time']),
        ]

class Location(models.Model):
    lat = models.FloatField()
    lon = models.FloatField()
    description = models.CharField(max_length=255, default='')
    def __str__(self):
        if self.description == '':
            return 'Unknown location'
        return self.description
    class Meta:
        app_label = 'locman'
        verbose_name = 'location'
        verbose_name_plural = 'locations'
        indexes = [
            models.Index(fields=['lat', 'lon']),
        ]

class Event(models.Model):
    timestart = models.DateTimeField()
    timeend = models.DateTimeField()
    location = models.ForeignKey(Location, on_delete=models.CASCADE, blank=True, null=True)
    def __distance(self, lat1, lon1, lat2, lon2):
        """ Returns the distance, in km, between lat1,lon1 and lat2,lon2. """
        radius = 6371.0 # km

        dlat = math.radians(lat2-lat1)
        dlon = math.radians(lon2-lon1)
        a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        d = radius * c

        return(d)

    def geojson(self):
        lasttime = datetime.datetime(1970, 1, 1, 0, 0, 0, tzinfo=pytz.UTC)
        lastlat = 0.0
        lastlon = 0.0
        minlat = 360.0
        minlon = 360.0
        maxlat = -360.0
        maxlon = -360.0
        track = []
        geo = []
        dist = 0.0
        for point in Position.objects.filter(time__gte=self.timestart).filter(time__lte=self.timeend):
            if ((lastlat != 0.0) & (lastlon != 0.0)):
                dist = dist + self.__distance(lastlat, lastlon, point.lat, point.lon)
            if (point.time - lasttime).total_seconds() > 90:
                if len(track) > 1:
                    geo.append(track)
                lastlat = 0.0
                lastlon = 0.0
                track = []
            data = [point.lon, point.lat]
            if (lastlat != point.lat) or (lastlon != point.lon):
                track.append(data)
                if point.lon < minlon:
                    minlon = point.lon
                if point.lon > maxlon:
                    maxlon = point.lon
                if point.lat < minlat:
                    minlat = point.lat
                if point.lat > maxlat:
                    maxlat = point.lat
            lasttime = point.time
            lastlat = point.lat
            lastlon = point.lon
        if len(track) > 1:
            geo.append(track)
        ret = {"type":"Feature", "bbox":[minlon, maxlat, maxlon, minlat], "properties":{"distance": dist}, "geometry":{"type":"MultiLineString","coordinates":geo}}
        return ret
    class Meta:
        app_label = 'locman'
        verbose_name = 'event'
        verbose_name_plural = 'events'
        indexes = [
            models.Index(fields=['timestart', 'timeend']),
            models.Index(fields=['location']),
        ]
