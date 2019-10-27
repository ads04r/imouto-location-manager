from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets

from .models import *
from .serializers import *
from .functions import extrapolate_position, calculate_speed

import datetime, pytz

class EventList(APIView):
    
    def get(self, request):
        data = Event.objects.all()
        serializer = EventSerializer(data, many=True)
        return Response(serializer.data)

    def post(self):
        pass

class PositionList(APIView):

    def get(self, request):
        data = Position.objects.all()[0]
        serializer = PositionSerializer(data, many=True)
        return Response(serializer.data)

class EventViewSet(viewsets.ViewSet):
    """
    The Event namespace is for querying location events.
    
        event - Get a list of the last known day's worth of events
        event/[timestamp] - Get the events for a specific day (format is YYYY-MM-DD)
        event/[id] - Get detailed information about a particular event
    """
    def list(self, request):
        lastevent = Event.objects.all().order_by('-timestart')[0]
        queryset = Event.objects.filter(timeend__gte=lastevent.timestart)
        serializer = EventSerializer(queryset, many=True)
        return Response(serializer.data)
        
    def retrieve(self, request, pk=None):
        f = pk.split('-')
        if len(f) == 3:
            dsyear = int(f[0])
            dsmonth = int(f[1])
            dsday = int(f[2])
            dts = datetime.datetime(dsyear, dsmonth, dsday, 0, 0, 0, tzinfo=pytz.UTC)
            dte = datetime.datetime(dsyear, dsmonth, dsday, 23, 59, 59, tzinfo=pytz.UTC)
            queryset = Event.objects.filter(timestart__lte=dte).filter(timeend__gte=dts)
            serializer = EventSerializer(queryset, many=True)
            return Response(serializer.data)
        else:
            id = int(pk)
            event = Event.objects.get(id=id)
            data = {"id": id, "timestart": event.timestart, "timeend": event.timeend, "geo": event.geojson()}
            return Response(data)

class PositionViewSet(viewsets.ViewSet):
    """
    The Position namespace is for querying raw location data.
    
        position - Get a list of the last ten explicit positions logged
        position/[timestamp] - Get the location for a specific timestamp (format is YYYYMMDDHHMMSS, always UTC)
    """
    def list(self, request):
        queryset = Position.objects.all()[0:10]
        serializer = PositionSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        ds = str(pk)
        dsyear = int(ds[0:4])
        dsmonth = int(ds[4:6])
        dsday = int(ds[6:8])
        dshour = int(ds[8:10])
        dsmin = int(ds[10:12])
        dssec = int(ds[12:])
        dt = datetime.datetime(dsyear, dsmonth, dsday, dshour, dsmin, dssec, tzinfo=pytz.UTC)
        # queryset = Position.objects.all()
        # pos = get_object_or_404(queryset, time=dt)
        try:
            pos = Position.objects.get(time=dt)
        except:
            pos = extrapolate_position(dt)
        if pos.speed is None:
            pos.speed = calculate_speed(pos)
            pos.save()
        serializer = PositionSerializer(pos)
        return Response(serializer.data)

