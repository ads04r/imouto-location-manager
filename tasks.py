from background_task import background
from .models import Position
from .functions import *
import datetime, pytz

@background(schedule=0)
def fill_locations():
    
    try:
        min_dt = Position.objects.filter(explicit=False).filter(source='cron').aggregate(Max('time'))['time__max']
    except:
        min_dt = Position.objects.aggregate(Min('time'))['time__min']
    max_dt = Position.objects.aggregate(Max('time'))['time__max']
    # med_dt = min_dt + datetime.timedelta(days=7)
    # if med_dt < max_dt:
        # max_dt = med_dt # ensure we don't go completely crazy with the extrapolating
    
    dt = min_dt + datetime.timedelta(minutes=5)
    while(dt < max_dt):
        try:
            pos = Position.objects.get(time=dt)
        except:
            pos = extrapolate_position(dt, 'cron')
            
        if pos.speed is None:
            pos.speed = calculate_speed(pos)
            pos.save()
            
        dt = dt + datetime.timedelta(seconds=60)

@background(schedule=0)
def import_uploaded_file(filename, source):
    
    if filename.lower().endswith('.gpx'):
        import_data(parse_file_gpx(filename, source), source)

    if filename.lower().endswith('.fit'):
        import_data(parse_file_fit(filename, source), source)

    dt = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) - datetime.timedelta(days=30)
    for pos in Position.objects.filter(time__gte=dt).filter(speed=None).order_by('time'):
        pos.speed = calculate_speed(pos)
        pos.save()
