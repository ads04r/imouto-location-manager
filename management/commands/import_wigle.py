from django.core.management.base import BaseCommand
from django.conf import settings
import os, sys, datetime, shutil, csv, pytz
from locman.models import Scan

def import_wigle_csv(filename):
	stats = []
	data = []
	headers = []
	with open(filename, encoding='iso-8859-1') as csvfile:
		fp = csv.reader(csvfile, delimiter=',', quotechar='"')
		for row in fp:
			if len(stats) == 0:
				stats = row
				continue
			if len(headers) == 0:
				headers = row
				continue
			if len(row) > len(headers):
				continue
			item = {}
			for i in range(0, len(row)):
				k = headers[i]
				v = row[i]
				item[k] = v
			data.append(item)
	if not('WigleWifi' in stats[0]):
		return []
	wifi_done = []
	bt_done = []
	ok_ct = 0
	for item in data:
		type = item['Type'].lower()
		lat = float(item['CurrentLatitude'])
		lon = float(item['CurrentLongitude'])
		ds = item['FirstSeen']
		mac = item['MAC']
		ssid = item['SSID']
		dt = datetime.datetime.strptime(ds, "%Y-%m-%d %H:%M:%S").replace(tzinfo=pytz.UTC)
		if type == 'wifi':
			if not(mac in wifi_done):
				wifi_done.append(mac)
		if type == 'bt':
			if not(mac in bt_done):
				bt_done.append(mac)
		try:
			record = Scan(time=dt, lat=lat, lon=lon, mac=mac, ssid=ssid, type=type)
			record.save()
		except:
			record = None
		if not(record is None):
			ok_ct = ok_ct + 1
	return [len(data), ok_ct, len(wifi_done), len(bt_done)]

class Command(BaseCommand):
	"""
	Command for importing Wigle CSV data into the location manager of Imouto.
	"""
	def add_arguments(self, parser):

		parser.add_argument("-i", "--input", action="store", dest="input_file", default="", help="The Wigle CSV file, containing scan data, to be imported.")

	def handle(self, *args, **kwargs):

		uploaded_file = os.path.abspath(kwargs['input_file'])
		temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
		temp_file = os.path.join(temp_dir, str(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")) + "_" + os.path.basename(uploaded_file))

		if ((uploaded_file == '') or (os.path.isdir(uploaded_file))):
			sys.stderr.write(self.style.ERROR("Input file must be specified using the --input switch. See help for more details.\n"))
			sys.exit(1)

		if not(os.path.exists(uploaded_file)):
			sys.stderr.write(self.style.ERROR("File not found: '" + uploaded_file + "'\n"))
			sys.exit(1)

		if not os.path.exists(temp_dir):
			os.makedirs(temp_dir)
		shutil.copyfile(uploaded_file, temp_file)

		ret = import_wigle_csv(temp_file)
		if len(ret) != 4:
			sys.stderr.write(self.style.ERROR("Input file could not be parsed. Is it proper Wigle CSV, and in ISO-8859-1 format?\n"))

		sys.stdout.write(self.style.SUCCESS("Successfully imported " + uploaded_file + "\n"))
		sys.stdout.write(str(ret[0]) + " records processed\n")
		sys.stdout.write(str(ret[2]) + " wifi stations found\n")
		sys.stdout.write(str(ret[3]) + " bluetooth stations found\n")
		sys.stdout.write(str(ret[1]) + " records added to the database\n")
