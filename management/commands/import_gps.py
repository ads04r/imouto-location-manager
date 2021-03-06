from django.core.management.base import BaseCommand
from django.conf import settings
from locman.tasks import *
import os, sys, datetime, shutil

class Command(BaseCommand):
	"""
	Command for importing GPS data into the location manager of Imouto, in various different formats.
	"""
	def add_arguments(self, parser):

		parser.add_argument("-i", "--input", action="store", dest="input_file", default="", help="The file, containing GPS data, to be imported.")
		parser.add_argument("-f", "--format", action="store", dest="input_format", default="", help="The type of the file being imported.", choices=['gpx', 'csv', 'fit'])
		parser.add_argument("-s", "--source", action="store", dest="input_source", default="", help="An identifier for the source of the imported GPS data. For example: phone_gps.")

	def handle(self, *args, **kwargs):

		uploaded_file = os.path.abspath(kwargs['input_file'])
		temp_dir = os.path.join(settings.MEDIA_ROOT, 'temp_uploads')
		temp_file = os.path.join(temp_dir, str(datetime.datetime.utcnow().strftime("%Y%m%d%H%M%S")) + "_" + os.path.basename(uploaded_file))
		file_source = kwargs['input_source']
		format = kwargs['input_format']

		if ((uploaded_file == '') or (os.path.isdir(uploaded_file))):
			sys.stderr.write(self.style.ERROR("Input file must be specified using the --input switch. See help for more details.\n"))
			sys.exit(1)

		if file_source == '':
			sys.stderr.write(self.style.ERROR("Data source must be specified using the --source switch. See help for more details.\n"))
			sys.exit(1)

		if not(os.path.exists(uploaded_file)):
			sys.stderr.write(self.style.ERROR("File not found: '" + uploaded_file + "'\n"))
			sys.exit(1)

		if not(format in ['', 'csv', 'fit', 'gpx']):
			sys.stderr.write(self.style.ERROR("Unknown file format: '" + format + "'\n"))
			sys.exit(1)

		if not os.path.exists(temp_dir):
			os.makedirs(temp_dir)
		shutil.copyfile(uploaded_file, temp_file)

		if format == '':
			import_uploaded_file(temp_file, file_source)
		else:
			import_uploaded_file(temp_file, file_source, format)
		sys.stdout.write(self.style.SUCCESS(uploaded_file + "\n"))
