from django.core.management.base import BaseCommand
from django.conf import settings
from locman.functions import import_data
import os, sys, datetime, pytz, json

class Command(BaseCommand):
	"""
	Command for importing flight path data from flighradar24.com
	"""
	def add_arguments(self, parser):

		parser.add_argument("-i", "--input", action="store", dest="input_file", default="", help="The file, containing JSON data downloaded from api.flightradar24.com, to be imported.")
		parser.add_argument("-o", "--offset", action="store", dest="offset", default="0", help="The offset (in days) for the flight data. Useful if you have the data for the correct flight but for the wrong day.")

	def handle(self, *args, **kwargs):

		downloaded_file = os.path.abspath(kwargs['input_file'])
		offset = int(kwargs['offset'])

		if ((downloaded_file == '') or (os.path.isdir(downloaded_file))):
			sys.stderr.write(self.style.ERROR("Input file must be specified using the --input switch. See help for more details.\n"))
			sys.exit(1)

		if not(os.path.exists(downloaded_file)):
			sys.stderr.write(self.style.ERROR("File not found: '" + downloaded_file + "'\n"))
			sys.exit(1)

		with open(downloaded_file) as fp:
			file_data = json.load(fp)

		data = []

		for point in file_data['result']['response']['data']['flight']['track']:

			dt = datetime.datetime.fromtimestamp(int(point['timestamp']) + (offset * 86400)).replace(tzinfo=pytz.UTC)
			ds = dt.strftime("%Y-%m-%d %H:%M:%S")
			lat = float(point['latitude'])
			lon = float(point['longitude'])

			item = {}
			item['date'] = dt
			item['lat'] = lat
			item['lon'] = lon
			data.append(item)

		import_data(data, 'flightradar24')
