from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse, Http404
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, viewsets

from .models import *
from .serializers import *
from .functions import extrapolate_position, calculate_speed
from .tasks import *
from background_task.models import Task

import datetime, pytz

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

class RouteViewSet(viewsets.ViewSet):
    """
    The Route namespace is for querying positions in batch, as a route
    """
    def list(self, request):
        queryset = []
        serializer = RouteSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        ds = str(pk)
        dssyear = int(ds[0:4])
        dssmonth = int(ds[4:6])
        dssday = int(ds[6:8])
        dsshour = int(ds[8:10])
        dssmin = int(ds[10:12])
        dsssec = int(ds[12:14])
        dseyear = int(ds[14:18])
        dsemonth = int(ds[18:20])
        dseday = int(ds[20:22])
        dsehour = int(ds[22:24])
        dsemin = int(ds[24:26])
        dsesec = int(ds[26:])
        dts = datetime.datetime(dssyear, dssmonth, dssday, dsshour, dssmin, dsssec, tzinfo=pytz.UTC)
        dte = datetime.datetime(dseyear, dsemonth, dseday, dsehour, dsemin, dsesec, tzinfo=pytz.UTC)
        event = Event(timestart=dts, timeend=dte)
        data = {"timestart": event.timestart, "timeend": event.timeend, "geo": event.geojson()}
        return Response(data)

@csrf_exempt
def upload(request):
    if request.method == 'POST':
        raise Http404("That was a POST")
    else:
        raise Http404("That was a GET")
