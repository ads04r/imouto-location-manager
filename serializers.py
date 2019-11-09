from rest_framework import serializers
from .models import *

class EventSerializer(serializers.ModelSerializer):

    class Meta:
        model = Event
        fields = ['id', 'timestart', 'timeend']

class PositionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Position
        fields = ['time','lat','lon','speed','explicit','source']

class RouteSerializer(serializers.ModelSerializer):
    
    class Meta:
        model = Position
        fields = ['time','lat','lon']