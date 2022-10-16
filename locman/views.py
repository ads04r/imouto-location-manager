from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from django.db import OperationalError
from rest_framework.decorators import api_view, renderer_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import MethodNotAllowed
from rest_framework import status, viewsets

from .models import *
from .serializers import *
from .functions import extrapolate_position, calculate_speed, get_last_position, get_source_ids, distance, get_location_events, get_process_stats
from .tasks import *
from background_task.models import Task

import datetime, pytz, json, os, sys

class EventViewSet(viewsets.ViewSet):
    """
    The Event namespace is for querying location events.
    
        event - Get a list of the last known day's worth of events
        event/[id] - Get detailed information about a particular event
        event/[timestamp] - Get the events for a specific day (format is YYYY-MM-DD)
        event/[timestamp]/[lat]/[lon] - Get the events at a location for a specific day
    """
    def list(self, request):
        lastevent = Event.objects.all().order_by('-timestart')[0]
        queryset = Event.objects.filter(timeend__gte=lastevent.timestart)
        serializer = EventSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        if ',' in pk:
            f = pk.split(',')
            lat = float(f[0])
            lon = float(f[1])
            queryset = Event.objects.none()
            serializer = EventSerializer(queryset, many=True)
            return Response(serializer.data)
        else:
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
        queryset = Position.objects.order_by('-time')[0:10]
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

class ElevationViewSet(viewsets.ViewSet):
    """
    The Elevation namespace is for querying height positions in batch, for displaying as a graph
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
        data = []
        lat = None
        lon = None
        dist = 0
        for pos in Position.objects.filter(time__gte=dts, time__lte=dte, explicit=True).exclude(elevation=None):
            if not(lat is None):
                dist = dist + distance(lat, lon, pos.lat, pos.lon)
            e = pos.elevation
            if e < 0:
                e = 0
            data.append((pos.time, dist, e))
            lat = pos.lat
            lon = pos.lon
        return Response(data)

@csrf_exempt
def upload(request):

    if Task.objects.count() == 0:
        fill_locations()

    if request.method == 'GET':
        sources = get_source_ids()
        data = {'tasks':[], 'sources':{}}
        for source in sources:
            data['sources'][source] = str(Position.objects.order_by('-time')[0].time.strftime("%Y-%m-%d"))
        for task in Task.objects.all():
            if task.queue != 'imports':
                continue
            item = {}
            item['id'] = task.task_hash
            item['time'] = int(task.run_at.timestamp())
            item['label'] = task.task_name
            item['parameters'] = json.loads(task.task_params)
            data['tasks'].append(item)
        response = HttpResponse(json.dumps(data), content_type='application/json')
        return response

    if request.method != 'POST':
        raise MethodNotAllowed(str(request.method))

    uploaded_file = request.FILES['uploaded_file']
    temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
    temp_file = os.path.join(temp_dir, str(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")) + "_" + uploaded_file.name)
    file_source = request.POST['file_source']
    file_format = ''
    if 'file_format' in request.POST:
        file_format = request.POST['file_format']
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    writer = open(temp_file, 'wb')
    for line in uploaded_file:
        writer.write(line)
    writer.close()
    
    data = {'file':uploaded_file.name, 'size':uploaded_file.size, 'type':uploaded_file.content_type, 'source':file_source}
    import_uploaded_file(temp_file, file_source, file_format)
    response = HttpResponse(json.dumps(data), content_type='application/json')
    return response

def process(request):
    
    if Task.objects.count() == 0:
        fill_locations()
    
    if request.method == 'GET':
        data = {'tasks':[], 'stats':{}}
        for task in Task.objects.all():
            if task.queue != 'process':
                continue
            item = {}
            item['id'] = task.task_hash
            item['time'] = int(task.run_at.timestamp())
            item['label'] = task.task_name
            item['parameters'] = json.loads(task.task_params)
            data['tasks'].append(item)
        data['stats'] = get_process_stats()
        response = HttpResponse(json.dumps(data), content_type='application/json')
        return response

    if request.method != 'POST':
        raise MethodNotAllowed(str(request.method))
        
@api_view(['GET'])
def locationevent(request, ds, lat, lon):
    """
    The Event namespace is for querying location events.
    
        event - Get a list of the last known day's worth of events
        event/[id] - Get detailed information about a particular event
        event/[timestamp] - Get the events for a specific day (format is YYYY-MM-DD)
        event/[timestamp]/[lat]/[lon] - Get the events at a location for a specific day
    """
    ret = []
    dss = str(ds).replace("-", "").strip()
    dssyear = int(dss[0:4])
    dssmonth = int(dss[4:6])
    dssday = int(dss[6:8])
    dts = datetime.datetime(dssyear, dssmonth, dssday, 0, 0, 0, tzinfo=pytz.UTC)
    dte = datetime.datetime(dssyear, dssmonth, dssday, 23, 59, 59, tzinfo=pytz.UTC)

    ret = get_location_events(dts, dte, lat, lon)

    serializer = EventSerializer(ret, many=True)
    response = Response(data=serializer.data)
    return response
