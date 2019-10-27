from django.db import models

# Create your models here.

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
        return []
    class Meta:
        app_label = 'locman'
        verbose_name = 'event'
        verbose_name_plural = 'events'
        indexes = [
            models.Index(fields=['timestart', 'timeend']),
            models.Index(fields=['location']),
        ]
