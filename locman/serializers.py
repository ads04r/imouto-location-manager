from rest_framework import serializers
from .models import *
from background_task.models import Task

class EventSerializer(serializers.ModelSerializer):

    class Meta:
        model = Event
        fields = ['timestart', 'timeend', 'lat', 'lon']

class PositionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Position
        fields = ['time','lat','lon','speed','explicit','source']

class RouteSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Position
        fields = ['time','lat','lon']
