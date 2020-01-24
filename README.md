Imouto Location Manager
=======================

The part of Imouto that manages locations. Obviously.

Imouto
------
Imouto is a life annotation system first introduced in my PhD thesis, and
later improved upon and referenced in several academic papers published by
myself and colleagues. Since I left the field of computer science research,
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




