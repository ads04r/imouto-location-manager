Imouto Location Manager
=======================

The part of Imouto that manages locations. Obviously.

Imouto
------
Imouto is a life annotation system first introduced in 
[my PhD thesis](https://eprints.soton.ac.uk/266554/1/thesis.pdf), and
later improved upon and referenced in several academic papers published by
[myself](https://eprints.soton.ac.uk/272324/1/websci11final.pdf) and
[colleagues](https://eprints.soton.ac.uk/346890/1/memorybook.pdf).
Since I left the field of computer science research,
Imouto has evolved as technology has changed. Now, rather than rely on
a companion app on a PDA for quantifiable life data, it gets the data from
a variety of different off-the-shelf tracking devices such as fitness
trackers and smartwatches. Instead of requiring a seperate Windows
application to import data from elsewhere, it now runs as background
tasks within a web application. I've also ported most of the code to
Python (specifically Django) rather than have a mish-mash of PHP, C# and
whatever else was required at the time.

For those interested, 'imouto' is the japanese word for 'little sister'.

Location Manager
----------------

The location manager is a Django app designed to run on the same server as
the viewer app (https://github.com/ads04r/imouto-viewer) but could run
independently if you need it to. The core functionality of Imouto has always
been around location data, and if you keep logs for every second of every
day, as I do, you end up with 86,400 records per day, which is 31,557,600
records per year. And as precise location data is never exact, and requires
a heck of a lot of maths to make useful, a 'wrapper' app to summarise the
data in the background while presenting more general observations quickly
to the viewer app was required.

The Location Manager app isn't particularly user friendly. It's intended
to be called mostly by the Viewer app, but you can do some useful querying
of your GPS data if you speak JSON.

Installation
------------

The location manager is a Django app. You can run it on its own server,
or on the same server as the viewer, with a different port number. If you
really want some un-necessary pain, you can try and join the viewer and
the location manager into the same Django project, but this isn't
recommended. Although this is how they were initially written, there are
many disadvantages in stability and performance.

1. (optional, but recommended) create a Python Virtual Environment (venv).

2. Clone the repository into a local directory, eg

   `git clone https://github.com/ads04r/imouto-location-manager.git imouto`

   will clone the repository into the local directory 'imouto'.

3. Change into the directory

   `cd imouto`

4. Install all the python requirements. I recomment using the python
   executable rather than pip on the command line because you can be sure
   you install it in the version of python you are using

   `python -m pip install -r requirements.txt`

5. Rename the `settings_local.py.dist` file in the imouto directory
   `settings_local.py` and edit it as appropriate. More docs have
   yet to be written, it's assumed for now that you know what you're
   doing.

6. If necessary, set up a database (MariaDB is officially supported but
   there's no reason PostGreSQL or SQLite won't work) and make sure
   `settings_local.py` and `database.conf` are populated accordingly.
   Again, it's assumed here you know what you're doing.

7. Create the migrations for the Django app

   `python manage.py makemigrations`

8. Run the migrations

   `python manage.py migrate`

9. From hereon in there are three things that need to be started.
   The main server, and two background process queues. I strongly
   recommend using Apache or Nginx rather than Django's built-in
   HTTP server, particularly if you're running in production, and
   writing systemd scripts for the two background queues. In the
   meantime each of the above can be started interactively as
   follows...

   `python manage.py runserver 0:8000`
   `python manage.py process_tasks --queue=process`
   `python manage.py provess_tasks --queue=imports`

   More docs to follow when I have time.


Usage - Importing Data
----------------------

There are two ways of importing a data file into the Location Manager. The
first is via a POST request, and this is intended to only be called from
the Viewer. The second method is via a management command.

    python manage.py import_gps -i [file] -s [source] ( -f [format] )

* `file` refers, obviously, to the file containing the GPS data you would
  like to import. This can be a GPX file, a simple CSV file of format
  timestamp-latitude-longitude, or a FIT file, most commonly created by
  Garmin hardware.
* `source` is a string stored alongside each location reading in the file
  that serves as an indicator as to how the data was measured. Despite
  being a required argument, this isn't actually used, and can be pretty
  much anything you like. But as someone who regularly experiments with
  different measuring methods and technology, it's useful to be able to
  say, for example, "delete all location values measured by that £5
  fitness tracker I got on Alibaba, I can't trust its accuracy". I suggest
  setting this to something descriptive like 'phone_gps' or 'garmin_watch'.
* `format` is optional, and refers to the format of the data in the file
  being imported. If you omit it, the importer guesses based on the
  file extension. It can be set to 'fit', 'csv' or 'gpx'. Handy if you're
  the sort of person who likes to give files unusual extensions.

Usage - Querying Data
---------------------

Once a new file or files have been imported, the background tasks spring
into action. They fill in inperpolated values and generate events based on
movement and previously queried locations. To actually query the data there's
a REST API generated by the Django REST Framework. This has a nice HTML
front-end which can be accessed by visiting /location-manager in a web
browser. From here, everything else is documented in-situ and has the
following views:

* `event` for querying location events, as generated by the background tasks.
  These may be queried by their unique ID (primary key), by day, or by
  day and location (eg if you know you went to a place on a particular day
  but need to know what time you arrived and left).
* `position` for quering a location by timestamp. If no location is available
  for the timestamp selected, it is interpolated. The data returned makes it
  clear when this has happened, the 'explicit' property will be false.
* `route` for returning a polyline of a route taken. This needs to be called
  with the start and end times of a journey, and returns a GeoJSON structure.
* `elevation` primarily for returning an elevation graph. This needs to be
  called with start and end times, and returns a list of objects consisting
  of a date stamp, a horizontal distance since the start of the route in
  metres, and a height also in metres.

