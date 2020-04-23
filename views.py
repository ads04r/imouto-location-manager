from django.shortcuts import render, get_object_or_404
from django.http import HttpResponse
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import MethodNotAllowed
from rest_framework import status, viewsets

from .models import *
from .serializers import *
from .functions import extrapolate_position, calculate_speed, get_last_position, get_source_ids
from .tasks import *
from background_task.models import Task

import datetime, pytz, json, os, sys

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
    
    if not os.path.exists(temp_dir):
        os.makedirs(temp_dir)
    writer = open(temp_file, 'wb')
    for line in uploaded_file:
        writer.write(line)
    writer.close()
    
    data = {'file':uploaded_file.name, 'size':uploaded_file.size, 'type':uploaded_file.content_type, 'source':file_source}
    import_uploaded_file(temp_file, file_source)
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
        data['stats']['last_calculated_positon'] = int(Position.objects.filter(explicit=False, source='cron').order_by('-time')[0].time.timestamp())
        data['stats']['last_generated_event'] = int(Event.objects.order_by('-timestart')[0].timestart.timestamp())
        response = HttpResponse(json.dumps(data), content_type='application/json')
        return response

    if request.method != 'POST':
        raise MethodNotAllowed(str(request.method))
        
