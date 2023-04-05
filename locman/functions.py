from django.db.models import Max, Min, Avg
from django.db.utils import OperationalError
from django.core.cache import cache
from xml.dom import minidom
from fitparse import FitFile
import datetime, math, csv, dateutil.parser, pytz, urllib.request, json
from tzlocal import get_localzone
from .models import Position, Event

def get_process_stats():

    now = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
    ret = {}

    if cache.has_key('last_calculated_position'):
        ret['last_calculated_position'] = int(cache.get('last_calculated_position'))
    else:
        try:
            ret['last_calculated_position'] = int(Position.objects.filter(explicit=False, source='cron').order_by('-time')[0].time.timestamp())
            cache.set('last_calculated_position', ret['last_calculated_position'], 86400)
        except IndexError:
            ret['last_calculated_position'] = int(now.timestamp())

    if cache.has_key('last_generated_event'):
        ret['last_generated_event'] = int(cache.get('last_generated_event'))
    else:
        try:
            ret['last_generated_event'] = int(Event.objects.order_by('-timestart')[0].timestart.timestamp())
            cache.set('last_generated_event', ret['last_generated_event'], 86400)
        except IndexError:
            ret['last_generated_event'] = int(now.timestamp())

    return ret

def generate_events(max_speed=2, max_length=300):

    ret = []
    try:
        dt = Event.objects.order_by('-timeend').first().timeend
    except:
        dt = None
    if dt is None:
        dt = datetime.datetime.utcnow().replace(tzinfo=pytz.UTC)
        ev = Event(timestart=dt, timeend=dt)
        ev.save()
        ret.append(ev)
        return ret
    pp = Position.objects.filter(time__gte=dt, speed__gt=max_speed).order_by('time').all()
    stops = []
    stops_refined = []
    for i in range(0, len(pp) - 4):
        buffer_before = (pp[i + 1].time - pp[i].time).total_seconds()
        event_length = (pp[i + 2].time - pp[i + 1].time).total_seconds()
        buffer_after = (pp[i + 3].time - pp[i + 2].time).total_seconds()
        if event_length >= max_length:
            if ((buffer_before < 60) & (buffer_after < 60)):
                #ev = Event(timestart=pp[i + 1].time, timeend=pp[i + 2].time)
                #ev.save()
                ev = [pp[i + 1].time, pp[i + 2].time]
                stops.append(ev)
    for n in stops:
        i = len(stops_refined) - 1
        if i < 0:
            stops_refined.append(n)
            continue
        dur = (n[0] - stops_refined[i][1]).total_seconds()
        if dur < max_length:
            stops_refined[i][1] = n[1]
        else:
            stops_refined.append(n)
    for n in stops_refined:
        ll = Position.objects.filter(time__gte=n[0], time__lte=n[1]).aggregate(Avg('lat'), Avg('lon'))
        e = Event(timestart=n[0], timeend=n[1], lat=ll['lat__avg'], lon=ll['lon__avg'])
        e.save()
        ret.append(e)
        cache.set('last_generated_event', int(e.timestart.timestamp()), 86400)

    return ret

def get_location_events(dts, dte, lat, lon, dist=0.05):

    minlat = float(lat) - dist
    maxlat = float(lat) + dist
    minlon = float(lon) - dist
    maxlon = float(lon) + dist

    ret = []

    starttime = dts
    lasttime = dts
    for position in Position.objects.filter(time__gte=dts - datetime.timedelta(hours=12), time__lte=dte + datetime.timedelta(hours=24), lat__gt=minlat, lat__lt=maxlat, lon__gt=minlon, lon__lt=maxlon).order_by('time'):
        if starttime == dts:
            starttime = position.time
            lasttime = position.time
        dist = distance(float(lat), float(lon), position.lat, position.lon)
        if dist > 100:
            continue
        if (position.time - lasttime).total_seconds() > 300:
            if ((starttime >= dts) & (starttime <= dte) & (starttime != lasttime)):
                item = {'timestart': starttime, 'timeend': lasttime}
                ret.append(item)
            starttime = position.time
        lasttime = position.time
    if starttime > dts:
        if ((starttime >= dts) & (starttime <= dte) & (starttime != lasttime)):
            item = {'timestart': starttime, 'timeend': lasttime}
            ret.append(item)

    return ret

def get_last_position(source=''):
    """ Returns a datetime referencing the last position in the user's data. Optionally, specify a data source ID to restrict the search to that source. """
    if source == '':
        try:
            latest = Position.objects.order_by('-time')[0].time
        except:
            latest = None
    else:
        try:
            latest = Position.objects.filter(source=source).order_by('-time')[0].time
        except:
            latest = None
    return latest

def get_last_event():
    """ Returns the start time of the last generated event. Or, if no events have been generated, the time of the last available data. """
    try:
        latest = Event.objects.order_by('-timeend')[0].timestart
    except:
        latest = get_last_position() # TODO change this to first?
    return latest

def parse_file_fit(filename, source='unknown'):
    """ Parses an ANT-FIT file. The source is just a string to uniquely identify a particular data source, such as 'my_smartwatch' or 'my_bike_tracker'. """
    data = []
    try:
        fit = FitFile(filename)
    except:
        return []
    tz = get_localzone()
    tz = pytz.UTC
    for record in fit.get_messages('record'):
        item = {}
        for recitem in record:
            k = recitem.name
            if ((k != 'position_lat') & (k != 'position_long') & (k != 'timestamp') & (k != 'enhanced_altitude')):
                continue
            v = {}
            v['value'] = recitem.value
            v['units'] = recitem.units
            if ((v['units'] == 'semicircles') & (not(v['value'] is None))):
                v['value'] = float(v['value']) * ( 180 / math.pow(2, 31) )
                v['units'] = 'degrees'
            item[k] = v
        if not('position_lat' in item):
            continue
        if not('position_long' in item):
            continue
        if not('timestamp' in item):
            continue
        if item['position_lat']['value'] is None:
            continue
        if item['position_long']['value'] is None:
            continue
        if item['timestamp']['value'].tzinfo is None or item['timestamp']['value'].utcoffset(item['timestamp']['value']) is None:
            item['timestamp']['value'] = tz.localize(item['timestamp']['value'])
            item['timestamp']['value'] = item['timestamp']['value'].replace(tzinfo=pytz.utc) - item['timestamp']['value'].utcoffset() # I like everything in UTC. Bite me.
        newitem = {}
        newitem['lat'] = item['position_lat']['value']
        newitem['lon'] = item['position_long']['value']
        if 'enhanced_altitude' in item:
            newitem['alt'] = float(item['enhanced_altitude']['value'])
        newitem['date'] = item['timestamp']['value']
        data.append(newitem)
    return data

def parse_file_gpx(filename, source='unknown'):
    """ Parses a GPX file. The source is just a string to uniquely identify a particular data source, such as 'phone' or 'fitness_tracker'. """
    data = []
    xml = minidom.parse(filename)
    for point in xml.getElementsByTagName('trkpt'):
        item = {}
        item['lat'] = point.attributes['lat'].value
        item['lon'] = point.attributes['lon'].value
        for timeval in point.getElementsByTagName('time'):
            item['date'] = dateutil.parser.parse(timeval.childNodes[0].nodeValue)
        for altval in point.getElementsByTagName('ele'):
            item['alt'] = float(altval.childNodes[0].nodeValue)
        data.append(item)
    return data

def parse_file_csv(filename, source='unknown', delimiter='\t'):
    """ Parses a CSV file. The columns must be in the format ISO8601 date, latitude, longitude, but the delimiter can be specified. """
    data = []
    with open(filename, 'r') as fp:
        csvreader = csv.reader(fp, delimiter=delimiter, quotechar='"')
        for row in csvreader:
            item = {}
            item['date'] = datetime.datetime.strptime(row[0].strip(" "), '%Y-%m-%d %H:%M:%S').replace(tzinfo=pytz.UTC)
            item['lat'] = float(row[1])
            item['lon'] = float(row[2])
            data.append(item)
    return data

def import_data(data, source='unknown'):
    """ Takes a parsed dataset from parse_file_* and imports the data into the database. The source is just a string to uniquely identify a particular data source, such as 'phone' or 'fitness_tracker'. """
    dt = datetime.datetime.now(pytz.utc)
    for row in data:
        if row['date'] < dt:
            dt = row['date']
    Position.objects.filter(time__gte=dt, explicit=False).delete()
    Event.objects.filter(timestart__gte=dt).delete()
    if cache.has_key('last_calculated_position'):
        cached_dt = cache.get('last_calculated_position')
        dt_i = int(dt.timestamp())
        if dt_i < cached_dt:
            cache.set('last_calculated_position', dt_i, 86400)
    Event.objects.filter(timeend__gte=dt).delete()
    for row in data:
        try:
            pos = Position.objects.get(time=row['date'])
            if ((pos.elevation is None) & ('alt' in row)):
                pos.elevation = float(row['alt'])
                pos.save()
        except:
            pos = Position(time=row['date'], lat=row['lat'], lon=row['lon'], explicit=True, source=source)
            if 'alt' in row:
                pos.elevation = float(row['alt'])
            pos.save()

def extrapolate_position(dt, source='realtime'):
    """ Returns an approximate position for a specified time for which no explicit location data exists. """
    posbefore = Position.objects.filter(time__lt=dt).order_by('-time')[0]
    posafter = Position.objects.filter(time__gt=dt).order_by('time')[0]
    trange = (posafter.time - posbefore.time).seconds
    tpoint = (dt - posbefore.time).seconds
    if trange == 0:
        lat = posbefore.lat
        lon = posbefore.lon
    else:
        ratio = tpoint / trange
        latrange = posafter.lat - posbefore.lat
        lonrange = posafter.lon - posbefore.lon
        lat = posbefore.lat + (latrange * ratio)
        lon = posbefore.lon + (lonrange * ratio)
    pos = Position(time=dt, lat=lat, lon=lon, explicit=False, source=source)
    pos.save()

    return(pos)

def distance(lat1, lon1, lat2, lon2):
    """ Returns the distance, in metres, between lat1,lon1 and lat2,lon2. """
    radius = 6371000 # metres

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    return(d)

def calculate_speed(pos):
    """ Calculates the speed being travelled by the user for a particular Position (which presumably has no existing speed data). """
    dt = pos.time
    posbefore = Position.objects.filter(time__lt=dt).order_by('-time')[0]
    time = (dt - posbefore.time).seconds
    dist = distance(posbefore.lat, posbefore.lon, pos.lat, pos.lon)
    
    if time == 0:
        return 0.0 # Avoid divide by zero errors
    
    return((dist / time) * 2.237) # Return in miles per hour

def populate():
    """ A function to be called from a background process that goes through the database ensuring there is at least one Position object for each minute of time, even if it has to calculate them. """
    try:
        min_dt = Position.objects.filter(explicit=False).filter(source='cron').aggregate(Max('time'))['time__max']
    except:
        min_dt = Position.objects.aggregate(Min('time'))['time__min']
    max_dt = Position.objects.aggregate(Max('time'))['time__max']

    dt = min_dt + datetime.timedelta(seconds=60)
    if(dt < max_dt):
        added = False
        while(not(added)):
            try:
                pos = Position.objects.get(time=dt)
            except:
                pos = extrapolate_position(dt, 'cron')
                added = True
            if pos.speed is None:
                pos.speed = calculate_speed(pos)
                pos.save()
            dt = dt + datetime.timedelta(seconds=60)
        return(pos)
    else:
        return(False)

def get_source_ids():
    """ Returns a list of all the strings relating to data sources that have been used to import data into the database. """
    ret = []
    for data in Position.objects.values('source').distinct():
        ret.append(data['source'])
    return ret
