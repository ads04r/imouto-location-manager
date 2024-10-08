from django.shortcuts import render
from django.http import HttpResponse
from django.conf import settings
from django.db import OperationalError
from django.db.models import Min, Max
from django.core.cache import cache
from rest_framework.decorators import api_view, renderer_classes
from django.views.decorators.csrf import csrf_exempt
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer
from rest_framework.exceptions import MethodNotAllowed, AuthenticationFailed
from rest_framework.parsers import JSONParser
from rest_framework import status, viewsets

from .models import UserProfile, Position, Event
from .serializers import EventSerializer, PositionSerializer, RouteSerializer
from .functions import extrapolate_position, calculate_speed, get_last_position, get_source_ids, distance, get_location_events, get_process_stats
from .tasks import generate_location_events, import_uploaded_file
from background_task.models import Task

import datetime, pytz, json, os, sys

class EventViewSet(viewsets.ViewSet):
    """
    The Event namespace is for querying location events.

        event - Get a list of the last known day's worth of events
        event/[timestamp] - Get the events for a specific day (format is YYYY-MM-DD)
        event/[timestamp]/[lat]/[lon] - Get the events at a location for a specific day
    """
    def list(self, request):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
        lastevent = Event.objects.filter(user=user.profile).order_by('-timestart')[0]
        dt = lastevent.timestart.replace(hour=0, minute=0, second=0)
        queryset = Event.objects.filter(user=user.profile, timeend__gte=dt)
        serializer = EventSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
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
                queryset = Event.objects.filter(timestart__lte=dte, timeend__gte=dts, user=user.profile)
                serializer = EventSerializer(queryset, many=True)
                return Response(serializer.data)
            else:
                id = int(pk)
                try:
                    event = Event.objects.get(id=id, user=user.profile)
                    data = {"id": id, "timestart": event.timestart, "timeend": event.timeend, "geo": event.geojson()}
                except:
                    data = {}
                return Response(data)


class PositionViewSet(viewsets.ViewSet):
    """
    The Position namespace is for querying raw location data.

        position - Get a list of the last ten explicit positions logged
        position/[timestamp] - Get the location for a specific timestamp

    Format of timestamp should be YYYYMMDDHHMMSS, always UTC
    """
    def list(self, request):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
        queryset = Position.objects.filter(user=user.profile).order_by('-time')[0:10]
        serializer = PositionSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
        ds = str(pk)
        dsyear = int(ds[0:4])
        dsmonth = int(ds[4:6])
        dsday = int(ds[6:8])
        dshour = int(ds[8:10])
        dsmin = int(ds[10:12])
        dssec = int(ds[12:])
        dt = datetime.datetime(dsyear, dsmonth, dsday, dshour, dsmin, dssec, tzinfo=pytz.UTC)
        try:
            pos = Position.objects.get(user, time=dt)
        except:
            pos = extrapolate_position(dt)
        if pos.speed is None:
            pos.speed = calculate_speed(pos)
            pos.save()
        serializer = PositionSerializer(pos)
        return Response(serializer.data)

class RouteViewSet(viewsets.ViewSet):
    """
    The Route namespace is for querying positions in batch, as a route.

        route/[time_from][time_to] - Generate a GeoJSON object describing the location data within a particular timespan.

    Format of time_from and time_to should be YYYYMMDDHHMMSS, always UTC
    """
    def list(self, request):
        queryset = []
        serializer = RouteSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
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
        event = Event(timestart=dts, timeend=dte, user=user.profile)
        data = {"timestart": event.timestart, "timeend": event.timeend, "geo": event.geojson()}
        return Response(data)

class BoundingBoxViewSet(viewsets.ViewSet):
    """
    The Bounding Box namespace is for querying the maximum and minimum latitude and longitude during a particular timespan. The return value is a four-element list of co-ordinates, in the GeoJSON bounding box array order.

        bbox/[time_from][time_to] - Return extreme points within a particular timespan.

    Format of time_from and time_to should be YYYYMMDDHHMMSS, always UTC
    """
    def list(self, request):
        queryset = []
        serializer = RouteSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
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
        ret = Position.objects.filter(user=user.profile, time__gte=dts, time__lte=dte).aggregate(max_lat=Max('lat'), min_lat=Min('lat'), max_lon=Max('lon'), min_lon=Min('lon'))
        data = [ret['min_lon'], ret['min_lat'], ret['max_lon'], ret['max_lat']]
        return Response(data)

class ElevationViewSet(viewsets.ViewSet):
    """
    The Elevation namespace is for querying height positions in batch, for displaying as a graph. The return value is a list of three-element lists containing timestamp, distance along route and elevation.

        elevation/[time_from][time_to] - Generate a list of distance and elevation data within a particular timespan.

    Format of time_from and time_to should be YYYYMMDDHHMMSS, always UTC
    """
    def list(self, request):
        queryset = []
        serializer = RouteSerializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, pk=None):
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response([])
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
        for pos in Position.objects.filter(user=user.profile, time__gte=dts, time__lte=dte, explicit=True).exclude(elevation=None):
            if not(lat is None):
                dist = dist + distance(lat, lon, pos.lat, pos.lon)
            e = pos.elevation
            if e < 0:
                e = 0
            data.append((pos.time, dist, e))
            lat = pos.lat
            lon = pos.lon
        return Response(data)

class ProcessViewSet(viewsets.ViewSet):
    """
    The process namespace queries the running of the Location Manager.

        process - Return an object containing relevant internal information.

    The object returned contains 'tasks', a list of background tasks in the processing queue, and 'stats', an object containing information about previously automatically generated data.
    """
    def list(self, request):
        data = {'tasks':[], 'stats':{}}
        user = request.user
        if not user.__class__.__name__ == 'User':
            return Response(data)
        for task in Task.objects.all():
            if task.queue != 'process':
                continue
            item = {}
            item['id'] = task.task_hash
            item['time'] = int(task.run_at.timestamp())
            item['label'] = task.task_name
            item['running'] = task.locked_by_pid_running()
            if item['running'] is None:
                item['running'] = False
            item['has_error'] = task.has_error()
            task_params = json.loads(task.task_params)
            item['user_id'] = task_params[0].pop(0)
            item['parameters'] = task_params
            data['tasks'].append(item)
        data['stats'] = get_process_stats(user)
        return Response(data)

@api_view(['GET', 'POST'])
def upload(request):
    """
    The import namespace queries the import status of the Location Manager.

        import - Return an object containing relevant internal information.

    The object returned contains 'tasks', a list of background tasks in the import queue, and
    'sources', an object containing all the manually specified sources of location information
    along with the date of the latest data from each source.
    """
    user = request.user
    if request.method == 'GET':
        data = {'tasks':[], 'sources':{}}
        if user.__class__.__name__ == 'User':
            data['user'] = user.username
        sources = get_source_ids()
        for source in sources:
            cache_key = 'last_' + source
            value = cache.get(cache_key)
            if value is None:
                try:
                    value = str(Position.objects.filter(user=user.profile, source=source).order_by('-time')[0].time.strftime("%Y-%m-%d"))
                except:
                    value = None
            if value is None:
                continue
            cache.set(cache_key, value, 86400)
            data['sources'][source] = value
        if user.__class__.__name__ == 'User':
            for task in Task.objects.all():
                if task.queue != 'imports':
                    continue
                item = {}
                item['id'] = task.task_hash
                item['time'] = int(task.run_at.timestamp())
                item['label'] = task.task_name
                item['running'] = task.locked_by_pid_running()
                if item['running'] is None:
                    item['running'] = False
                item['has_error'] = task.has_error()
                task_params = json.loads(task.task_params)
                item['user_id'] = task_params[0].pop(0)
                item['parameters'] = task_params
                data['tasks'].append(item)
            generate_location_events(user.pk)
        response = HttpResponse(json.dumps(data), content_type='application/json')
        return response

    if request.method != 'POST':
        raise MethodNotAllowed(str(request.method))

    if not user.__class__.__name__ == 'User':
        return AuthenticationFailed("This request requires a valid user to be logged in.")

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
    import_uploaded_file(user.pk, temp_file, file_source, file_format)
    response = HttpResponse(json.dumps(data), content_type='application/json')
    return response

@api_view(['GET'])
def locationevent(request, ds, lat, lon):
    """
    The Event namespace is for querying location events.

        event - Get a list of the last known day's worth of events
        event/[id] - Get detailed information about a particular event
        event/[timestamp] - Get the events for a specific day (format is YYYY-MM-DD)
        event/[timestamp]/[lat]/[lon] - Get the events at a location for a specific day
    """
    user = request.user
    if not user.__class__.__name__ == 'User':
        return Response([])
    ret = []
    dss = str(ds).replace("-", "").strip()
    dssyear = int(dss[0:4])
    dssmonth = int(dss[4:6])
    dssday = int(dss[6:8])
    dts = datetime.datetime(dssyear, dssmonth, dssday, 0, 0, 0, tzinfo=pytz.UTC)
    dte = datetime.datetime(dssyear, dssmonth, dssday, 23, 59, 59, tzinfo=pytz.UTC)

    ret = get_location_events(user, dts, dte, lat, lon)

    serializer = EventSerializer(ret, many=True)
    response = Response(data=serializer.data)
    return response
