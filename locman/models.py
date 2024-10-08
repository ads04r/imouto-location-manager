from django.db import models
from django.contrib.auth.models import User
from django.conf import settings
from django.db.models.signals import post_save
from django.dispatch import receiver
from rest_framework.authtoken.models import Token
from macaddress.fields import MACAddressField
import datetime, pytz, math, json

def friendly_time(seconds):
	s = int(seconds)
	if s < 60:
		return str(s) + " seconds"
	m = int(seconds / 60)
	s = s - (m * 60)
	if m < 60:
		if s == 0:
			return str(m) + " minutes"
		else:
			return str(m) + " minutes, " + str(s) + " seconds"
	h = int(m / 60)
	m = m - (h * 60)
	if m == 0:
		return str(h) + " hours"
	else:
		if s == 0:
			return str(h) + " hours, " + str(m) + " minutes"
		else:
			return str(h) + " hours, " + str(m) + " minutes, " + str(s) + " seconds"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    token = models.ForeignKey(Token, null=False, on_delete=models.CASCADE)
    def __str__(self):
        return str(self.user.username)

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        token = Token.objects.create(user=instance)
        UserProfile.objects.create(user=instance, token=token)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    instance.profile.save()

class Scan(models.Model):
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    time = models.DateTimeField()
    ssid = models.CharField(max_length=255, default='')
    mac = MACAddressField(null=True, blank=True)
    type = models.SlugField(max_length=32, default='wifi')
    user = models.ForeignKey(UserProfile, null=False, on_delete=models.CASCADE, related_name='scans')
    def __str__(self):
        ret = str(self.ssid)
        if ret == '':
            ret = str(self.mac)
        return ret
    class Meta:
        app_label = 'locman'
        verbose_name = 'scan'
        verbose_name_plural = 'scans'
        indexes = [
            models.Index(fields=['lat', 'lon']),
            models.Index(fields=['ssid']),
            models.Index(fields=['mac']),
            models.Index(fields=['type']),
            models.Index(fields=['time'])
        ]
        constraints = [
            models.UniqueConstraint(fields=['mac', 'time'], name='unique_mac_time')
        ]

class Position(models.Model):
    lat = models.FloatField()
    lon = models.FloatField()
    elevation = models.FloatField(null=True, blank=True)
    time = models.DateTimeField(unique=True)
    speed = models.IntegerField(blank=True, null=True)
    explicit = models.BooleanField(default=True)
    source = models.SlugField(max_length=32)
    user = models.ForeignKey(UserProfile, null=False, on_delete=models.CASCADE, related_name='positions')
    class Meta:
        app_label = 'locman'
        verbose_name = 'position'
        verbose_name_plural = 'positions'
        indexes = [
            models.Index(fields=['lat', 'lon']),
            models.Index(fields=['speed']),
            models.Index(fields=['explicit']),
            models.Index(fields=['source']),
        ]
        constraints = [
            models.UniqueConstraint(fields=['time', 'source', 'explicit'], name='locman_time_source_expl_uniq')
        ]

class Event(models.Model):
    timestart = models.DateTimeField()
    timeend = models.DateTimeField()
    lat = models.FloatField(null=True, blank=True)
    lon = models.FloatField(null=True, blank=True)
    amenities_data = models.TextField(default="[]")
    user = models.ForeignKey(UserProfile, null=False, on_delete=models.CASCADE, related_name='events')
    @property
    def amenities(self):
        if self.pk:
            return json.loads(self.amenities_data)
        ret = nearest_amenities(e.lat, e.lon)
        self.amenities_data = json.dumps(ret)
        return ret
    def __str__(self):
        return self.timestart.strftime("%Y-%m-%d %H:%M:%S") + " | " + str(self.timeend - self.timestart)
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
        poi = []

        max_speed = [0, 0.0, 0.0, None]
        max_height = [0, 0.0, 0.0, None]
        min_height = 9999

        for point in Position.objects.filter(time__gte=self.timestart).filter(time__lte=self.timeend):
            if not(point.speed is None):
                if point.speed > max_speed[0]:
                    max_speed = [point.speed, point.lat, point.lon, point.time.astimezone(pytz.timezone(settings.TIME_ZONE))]
            if not(point.elevation is None):
                if point.elevation < min_height:
                    min_height = point.elevation
                if point.elevation > max_height[0]:
                    max_height = [point.elevation, point.lat, point.lon, point.time.astimezone(pytz.timezone(settings.TIME_ZONE))]
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

        events = Event.objects.filter(timestart__gte=self.timestart, timeend__lte=self.timeend)
        if max_speed[0] > 10:
            poi.append({"type": "Point", "coordinates": [max_speed[2], max_speed[1]], "properties": {"type": "poi", "time": max_speed[3], "label": "Maximum speed " + str(max_speed[0]) + "mph at " + str(max_speed[3].strftime('%H:%M:%S'))}})
        if not(max_height[3] is None):
            height_diff = max_height[0] - min_height
            if ((height_diff > 50) or (max_height[0] > 200)):
                poi.append({"type": "Point", "coordinates": [max_height[2], max_height[1]], "properties": {"type": "poi", "time": max_height[3], "label": "Maximum elevation " + str(int(max_height[0])) + "m at " + str(max_height[3].strftime('%H:%M:%S'))}})

        polyline = {"type":"MultiLineString","coordinates":geo}
        if events.count() + len(poi) == 0:
            geometry = polyline
        else:
            geometry = {"type": "GeometryCollection", "geometries": [polyline]}
            for p in poi:
                geometry['geometries'].append(p)
            for event in events:
                geometry['geometries'].append({"type": "Point", "coordinates": [event.lon, event.lat], "properties": {"type": "stop", "arrive": event.timestart, "leave": event.timeend, "label": "Stopped for " + friendly_time((event.timeend - event.timestart).total_seconds())}})
        ret = {"type":"Feature", "bbox":[minlon, maxlat, maxlon, minlat], "properties":{"distance": dist}, "geometry":geometry}
        return ret
    class Meta:
        app_label = 'locman'
        verbose_name = 'event'
        verbose_name_plural = 'events'
        indexes = [
            models.Index(fields=['timestart', 'timeend']),
        ]
