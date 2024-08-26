from background_task import background
from .models import Position
from django.contrib.auth.models import User
from django.db.models import Max, Min, Avg
from django.core.cache import cache
from background_task.models import Task
from .functions import generate_events, extrapolate_position, calculate_speed
from .functions import parse_file_fit, parse_file_gpx, parse_file_csv, import_data
import datetime, pytz, os

@background(schedule=0, queue='process')
def generate_location_events(user_id):
    """
    A background task to assist the generation of location proximity events. The Location Manager doesn't
    know about the places defined in the Viewer, but it can tell you when and where the user stopped for
    more than a particular amount of time. The Viewer can check this in order to create loc_prox events.
    """
    if Task.objects.filter(queue='process', task_name__icontains='tasks.generate_location_events').count() > 1:
        return # If there's already an instance of this task running or queued, don't start another.
    if Task.objects.filter(queue='process', task_name__icontains='tasks.fill_locations').count() > 1:
        generate_location_events(user_id, schedule=60) # If a fill_locations task is running or queued, defer for 60 seconds.
        return
    if Task.objects.filter(queue='imports', task_name__icontains='tasks.import_uploaded_file').count() > 0:
        generate_location_events(user_id, schedule=60) # If there are imports running or queued, quit and reschedule for 60 seconds time.
        return
    user = User.objects.get(pk=user_id)
    generate_events(user)

@background(schedule=0, queue='process')
def fill_locations(user_id):
    """
    A background task for going through the explicitly imported position data and filling in any gaps by
    calling extrapolate_position. If this task is complete to the best of our ability, call the function
    for generating events.
    """
    user = User.objects.get(pk=user_id)

    if Task.objects.filter(queue='process', task_name__icontains='tasks.fill_locations').count() > 1:
        return # If there's already an instance of this task running, don't start another.
    if Task.objects.filter(queue='imports', task_name__icontains='tasks.import_uploaded_file').count() > 1:
        fill_locations(user_id, schedule=60)
        return # Hold off if we're still importing files
    try:
        min_dt = Position.objects.filter(user=user.profile, explicit=False, source='cron').aggregate(Max('time'))['time__max']
    except:
        min_dt = None
    if min_dt is None:
        min_dt = Position.objects.filter(user=user.profile).aggregate(Min('time'))['time__min']
    max_dt = Position.objects.filter(user=user.profile).aggregate(Max('time'))['time__max']
    if max_dt is None: # The database is probably empty, so just quit quietly
        return
    med_dt = min_dt + datetime.timedelta(days=28)
    is_med = False
    if med_dt < max_dt:
        is_med = True
        max_dt = med_dt # ensure we don't go completely crazy with the extrapolating
    if Task.objects.filter(queue='imports', task_name__icontains='tasks.import_uploaded_file', locked_by=None).count() > 0:
        fill_locations(user_id, schedule=60) # If there are imports running, quit and reschedule for 60 seconds time
        return
    if Task.objects.filter(queue='imports', task_name__icontains='tasks.import_uploaded_file').count() > 1:
        fill_locations(user_id, schedule=60) # If there are multiple imports queued, quit and reschedule for 60 seconds time
        return

    dt = min_dt + datetime.timedelta(minutes=5)
    addcount = 0
    while(dt < max_dt):
        try:
            pos = Position.objects.get(user=user.profile, time=dt)
        except:
            pos = extrapolate_position(user, dt, 'cron')
            if pos:
                addcount = addcount + 1

        if pos.speed is None:
            pos.speed = calculate_speed(pos)
            pos.save()

        if cache.has_key('last_calculated_position'):
            last_max = cache.get('last_calculated_position')
            di = dt.timestamp()
            if di > last_max:
                cache.set('last_calculated_position', di, 86400)

        dt = dt + datetime.timedelta(seconds=60)

    if is_med:
        fill_locations(user_id, schedule=60) # If there are still explicit locations stored, quit and reschedule for 60 seconds time
    else:
        generate_location_events(user_id) # Otherwise generate some events

@background(schedule=0, queue='imports')
def import_uploaded_file(user_id, filename, source, format=""):
    """
    A background task for importing a data file, previously uploaded via a POST to
    the web interface. Once the import is complete, the function calculates the speed
    for all imported position values.

    :param filename: The path of the uploadedfile to import.
    :param source: A string representing the source of the file for future provenance checking, eg 'phone_gps'.
    """
    user = User.objects.get(pk=user_id)

    if Task.objects.filter(queue='process', task_name__icontains='tasks.fill_locations').count() > 1:
        import_uploaded_file(user_id, filename, source, format, schedule=60) # If a fill_locations task is running or queued, defer for 60 seconds.
        return
    if format == '':

        if filename.lower().endswith('.gpx'):
            import_data(user, parse_file_gpx(filename, source), source)
        if filename.lower().endswith('.fit'):
            import_data(user, parse_file_fit(filename, source), source)
        if filename.lower().endswith('.csv'):
            import_data(user, parse_file_csv(filename, source), source)
        if filename.lower().endswith('.txt'):
            import_data(user, parse_file_csv(filename, source), source)

    else:

        if format == 'gpx':
            import_data(user, parse_file_gpx(filename, source), source)
        if format == 'fit':
            import_data(user, parse_file_fit(filename, source), source)
        if format == 'csv':
            import_data(user, parse_file_csv(filename, source), source)

    if os.path.exists(filename):
        os.remove(filename)

    dt = datetime.datetime.utcnow().replace(tzinfo=pytz.utc) - datetime.timedelta(days=30)
    for pos in Position.objects.filter(user=user.profile, time__gte=dt, speed=None).order_by('time'):
        pos.speed = calculate_speed(pos)
        pos.save()

    fill_locations(user_id) # Once we're done, call the fill locations task.

