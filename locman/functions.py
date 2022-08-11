from django.db.models import Max, Min
from django.db.utils import OperationalError
from xml.dom import minidom
from fitparse import FitFile
import datetime, math, csv, dateutil.parser, pytz, urllib.request, json
from tzlocal import get_localzone
from .models import Position, Event, Location

def get_location_events(dts, dte, lat, lon, dist=0.05):

    minlat = float(lat) - dist
    maxlat = float(lat) + dist
    minlon = float(lon) - dist
    maxlon = float(lon) + dist

    ret = []

    try:
        local_loc = Location.objects.get(lat=lat, lon=lon)
    except:
        local_loc = Location(lat=lat, lon=lon, description='')
        local_loc.save()
    if local_loc.description == '':
        description = get_location_description(lat, lon)
        if description == '':
            description = 'Unknown Location'
        if len(description) > 255:
            description = description[0:255]
        local_loc.description = description
        try:
            local_loc.save()
        except OperationalError:
            local_loc.description = 'Unknown Location'
            local_loc.save()

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
                item = {'timestart': starttime, 'timeend': lasttime, 'description': local_loc.description}
                ret.append(item)
            starttime = position.time
        lasttime = position.time
    if starttime > dts:
        if ((starttime >= dts) & (starttime <= dte) & (starttime != lasttime)):
            item = {'timestart': starttime, 'timeend': lasttime, 'description': local_loc.description}
            ret.append(item)

    return ret

def get_location_description(lat, lon):
    url = "https://nominatim.openstreetmap.org/search.php?q=" + str(lat) + "%2C" + str(lon) + "&polygon_geojson=1&format=jsonv2"
    request = urllib.request.urlopen(url)
    if(request.getcode() != 200):
        return ""
    data = json.loads(request.read())
    if len(data) == 0:
        return ""
    if 'display_name' in data[0]:
        return data[0]['display_name']
    return ""

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
    Position.objects.filter(time__gte=dt).filter(explicit=False).delete()
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
