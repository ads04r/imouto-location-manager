from rest_framework import serializers
from .models import *

class EventSerializer(serializers.ModelSerializer):

    class Meta:
        model = Event
        fields = '__all__'

class PositionSerializer(serializers.ModelSerializer):

    class Meta:
        model = Position
        fields = ['time','lat','lon','speed','explicit','source']