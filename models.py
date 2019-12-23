from django.db import models
import datetime, pytz

class Position(models.Model):
    lat = models.FloatField()
    lon = models.FloatField()
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
    description = models.CharField(max_length=128, default='')
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
        for point in Position.objects.filter(time__gte=self.timestart).filter(time__lte=self.timeend):
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
        ret = {"type":"Feature", "bbox":[minlon, maxlat, maxlon, minlat], "properties":{}, "geometry":{"type":"MultiLineString","coordinates":geo}}
        return ret
    class Meta:
        app_label = 'locman'
        verbose_name = 'event'
        verbose_name_plural = 'events'
        indexes = [
            models.Index(fields=['timestart', 'timeend']),
            models.Index(fields=['location']),
        ]
