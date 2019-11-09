from django.db.models import Max, Min
from xml.dom import minidom
from fitparse import FitFile
import datetime, math, csv, dateutil.parser, pytz, math
from tzlocal import get_localzone
from .models import Position, Event

def make_new_events():
    
    lastpos = get_last_position()
    if(lastpos is None):
        return
    lastev = get_last_event()
    if lastev >= lastpos:
        return
    
# 43118 | 2017-07-27 17:09:00 | 2017-07-27 17:16:00

    limit = lastev + datetime.timedelta(days=7)
    for pos in Position.objects.filter(time__gte=lastev).filter(time__lt=limit).filter(speed=None):
        print(pos.time)
        pos.speed = calculate_speed(pos)
        pos.save()

    lastdt = lastev
    for pos in Position.objects.filter(time__gte=lastev).filter(time__lt=limit).filter(speed=0).order_by('time'):
        dt = pos.time
        dist = (dt - lastdt).total_seconds()
        if dist > 360:
            print("=======================================================");
            ev = Event(timestart=lastdt, timeend=dt)
            ev.save()
        print(str(pos.time) + '\t' + str(dist) + '\t' + str(pos.lat) + ', ' + str(pos.lon))
        lastdt = dt

def get_last_position():

    try:
        latest = Position.objects.order_by('-time')[0].time
    except:
        latest = None
    return latest

def get_last_event():
    
    try:
        latest = Event.objects.order_by('-timeend')[0].timestart
    except:
        latest = Position.objects.order_by('time')[0].time
    return latest

def parse_file_fit(filename, source='unknown'):
    
    data = []
    fit = FitFile(filename)
    tz = get_localzone()
    tz = pytz.UTC
    for record in fit.get_messages('record'):
        item = {}
        for recitem in record:
            k = recitem.name
            if ((k != 'position_lat') & (k != 'position_long') & (k != 'timestamp')):
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
        newitem['date'] = item['timestamp']['value']
        data.append(newitem)
    return data

def parse_file_gpx(filename, source='unknown'):
    
    data = []
    xml = minidom.parse(filename)
    for point in xml.getElementsByTagName('trkpt'):
        item = {}
        item['lat'] = point.attributes['lat'].value
        item['lon'] = point.attributes['lon'].value
        for timeval in point.getElementsByTagName('time'):
            item['date'] = dateutil.parser.parse(timeval.childNodes[0].nodeValue)
        data.append(item)
    return data

def parse_file_csv(filename, source='unknown', delimiter='\t'):
    
    data = []
    with open(filename, 'r') as fp:
        csvreader = csv.reader(fp, delimiter=delimiter, quotechar='"')
        for row in csvreader:
            item = {}
            item['date'] = datetime.datetime.strptime( row[0] + ' UTC', '%Y-%m-%d %H:%M:%S %Z')
            item['lat'] = float(row[1])
            item['lon'] = float(row[2])
            data.append(item)
    return data

def import_data(data, source='unknown'):
    
    dt = datetime.datetime.now(pytz.utc)
    for row in data:
        if row['date'] < dt:
            dt = row['date']
    Position.objects.filter(time__gte=dt).filter(explicit=False).delete()
    Event.objects.filter(timeend__gte=dt).delete()
    for row in data:
        try:
            pos = Position.objects.get(time=row['date'])
        except:
            pos = Position(time=row['date'], lat=row['lat'], lon=row['lon'], explicit=True, source=source)
            pos.save()

def extrapolate_position(dt, source='realtime'):

    posbefore = Position.objects.filter(time__lt=dt).order_by('-time')[0]
    posafter = Position.objects.filter(time__gt=dt).order_by('time')[0]
    trange = (posafter.time - posbefore.time).seconds
    tpoint = (dt - posbefore.time).seconds
    ratio = tpoint / trange
    latrange = posafter.lat - posbefore.lat
    lonrange = posafter.lon - posbefore.lon
    lat = posbefore.lat + (latrange * ratio)
    lon = posbefore.lon + (lonrange * ratio)
    pos = Position(time=dt, lat=lat, lon=lon, explicit=False, source=source)
    pos.save()
    
    return(pos)

def distance(lat1, lon1, lat2, lon2):

    radius = 6371000 # metres

    dlat = math.radians(lat2-lat1)
    dlon = math.radians(lon2-lon1)
    a = math.sin(dlat/2) * math.sin(dlat/2) + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2) * math.sin(dlon/2)
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
    d = radius * c

    return(d)

def calculate_speed(pos):

    dt = pos.time
    posbefore = Position.objects.filter(time__lt=dt).order_by('-time')[0]
    time = (dt - posbefore.time).seconds
    dist = distance(posbefore.lat, posbefore.lon, pos.lat, pos.lon)
    
    if time == 0:
        return 0.0 # Avoid divide by zero errors
    
    return((dist / time) * 2.237) # Return in miles per hour

def populate():
    
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
