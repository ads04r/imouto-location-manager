from background_task import background
from .models import Position
from .functions import *
import datetime, pytz, os

@background(schedule=0, queue='process')
def fill_locations():
    """ A background task for going through the explicitly imported position data and filling in any gaps by calling extrapolate_position. If this task is complete to the best of our ability, call the function for generating events. """
    try:
        min_dt = Position.objects.filter(explicit=False).filter(source='cron').aggregate(Max('time'))['time__max']
    except:
        min_dt = Position.objects.aggregate(Min('time'))['time__min']
    max_dt = Position.objects.aggregate(Max('time'))['time__max']
    if max_dt is None: # The database is probably empty, so just quit quietly
        return
    med_dt = min_dt + datetime.timedelta(days=7)
    if med_dt < max_dt:
        max_dt = med_dt # ensure we don't go completely crazy with the extrapolating

    dt = min_dt + datetime.timedelta(minutes=5)
    addcount = 0
    while(dt < max_dt):
        try:
            pos = Position.objects.get(time=dt)
        except:
            pos = extrapolate_position(dt, 'cron')
            if pos:
                addcount = addcount + 1

        if pos.speed is None:
            pos.speed = calculate_speed(pos)
            pos.save()

        dt = dt + datetime.timedelta(seconds=60)

#    if addcount == 0:
#        make_new_events()

@background(schedule=0, queue='imports')
def import_uploaded_file(filename, source, format=""):
    """ A background task for importing a data file, previously uploaded via a POST to the web interface. Once the import is complete, the function calculates the speed for all imported position values. """
    if format == '':

        if filename.lower().endswith('.gpx'):
            import_data(parse_file_gpx(filename, source), source)
        if filename.lower().endswith('.fit'):
            import_data(parse_file_fit(filename, source), source)
        if filename.lower().endswith('.csv'):
            import_data(parse_file_csv(filename, source), source)
        if filename.lower().endswith('.txt'):
            import_data(parse_file_csv(filename, source), source)

    else:

        if format == 'gpx':
            import_data(parse_file_gpx(filename, source), source)
        if format == 'fit':
            import_data(parse_file_fit(filename, source), source)
        if format == 'csv':
            import_data(parse_file_csv(filename, source), source)

    if os.path.exists(filename):
        os.remove(filename)

    dt = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) - datetime.timedelta(days=30)
    for pos in Position.objects.filter(time__gte=dt).filter(speed=None).order_by('time'):
        pos.speed = calculate_speed(pos)
        pos.save()

