#!/usr/bin/python

# JPEG2PDF - convert image files to JPEG format and combine them into a PDF
#  file
#
# © 2022 Nicholas Campbell
#
# This program uses the img2pdf module:
# https://pypi.org/project/img2pdf/

DEBUG = True					# If True, print messages for debugging
								# purposes
jpeg_compression_quality = 75	# Default JPEG compression quality value
recompress_all_jpegs = False	# If True, always use recompressed JPEGs, even
								# if the size of the recompressed file is
								# greater than the original file

# Import built-in modules
import argparse
import decimal
import glob
from io import BytesIO
import os.path
import sys
import tempfile

# Import external packages
import_module_error_message = 'Unable to import {0}. Please check that it has \
been installed correctly. Maybe you have forgotten to activate a virtual \
environment?'

# img2pdf installs pikepdf and Pillow automatically
try:
	import img2pdf
	import pikepdf
	import PIL
	from PIL import Image
except ModuleNotFoundError as ex:
	print(import_module_error_message.format('img2pdf', file=sys.stderr))
	quit()


# ---------
# Functions
# ---------

def _parse_arguments(args):
	"""Parse the command-line arguments."""
	argparser = argparse.ArgumentParser(add_help=False)

	# Set positional arguments
	argparser.add_argument('input_files', metavar='input_file', nargs='+',
		help='image files to be added to the PDF document')
	argparser.add_argument('output_file', nargs=1,
		help='the PDF file to write')

	argparser.add_argument('-h', '--help', '-?', action='help',
		help='show this help message and exit')
	argparser.add_argument('-a', '--author', metavar='name',
		help='set the author of the PDF document')
	argparser.add_argument('-t', '--title', metavar='title',
		help='set the title of the PDF document')

	# Set JPEG compression settings
	viewer_argparser = argparser.add_argument_group(
		'JPEG compression settings (optional)',
		description='These settings control the compression of images when \
they are being converted to JPEG format.')
	viewer_argparser.add_argument('-q', '--quality', metavar='quality',
		help=f'set the compression quality when (re)compressing images \
(1=worst, 100=best); the default is {jpeg_compression_quality}')

	# Set magnification arguments
	viewer_argparser = argparser.add_argument_group(
		'viewer settings (optional)',
		description='These settings control how the PDF file is displayed \
when it is opened in a PDF viewer.')
	viewer_argparser.add_argument('--fit-horizontal',
		action='append_const', dest='magnification', const='FitH',
		help='fit the page to the width of the window')
	viewer_argparser.add_argument('--fit-vertical',
		action='append_const', dest='magnification', const='FitV',
		help='fit the page to the height of the window')
	viewer_argparser.add_argument('--fit-window',
		action='append_const', dest='magnification', const='Fit',
		help='fit the entire page within the window')

	# Set page mode arguments
	viewer_argparser.add_argument('--show-thumbnails', action='append_const',
		dest='page_mode', const='UseThumbs',
		help=f'show thumbnails for each page')

	# Set page numbering arguments
	page_numbering_argparser = argparser.add_argument_group(
		'page numbering settings (optional)',
		description='These settings control how the pages of the PDF file are \
numbered and displayed.')
	page_numbering_argparser.add_argument('-p', '--page-numbering',
		metavar='format_string', nargs=1,
		help='set the formatting of page numbers (e.g. %%D for Arabic \
numerals (1, 2, 3...), %%r for lower case Roman numerals (i, ii, iii...), \
%%A for upper case letters (A, B, C...))')
	page_numbering_argparser.add_argument('--first-page-number',
		metavar='page',
		help='set the number of the first page of the PDF file')

	return argparser.parse_args(args)


def parse_page_number_formatting_string(page_format):
	"""Parse a suitably formatted string for specifying the numbering style of pages
in a PDF file.

Examples:
%D - display page numbers in normal Arabic numerals (i.e. 1, 2, 3, etc.).
%r - display page numbers in lower case Roman numerals (i.e. i, ii, iii, etc.);
     use %R for upper case.
%a - display page numbers as lower case Latin letters (i.e. a, b, c..., z, aa,
     bb, cc, etc.); use %A for upper case.
A-%D - display page numbers as normal Arabic numerals and place 'A-' before
       each number.

See section 3.7.1 of the Adobe PDF v1.3 Reference for more details.

Parameters:
page_format: The formatting string.

Returns:
prefix (str): The prefix to be placed before each page number.
style (str): The style to use for displaying each page number, prefixed with a
    forward slash (/).
"""
	prefix = None					# Prefix to add before each page number
	style = None					# The style to use when displaying page
									# numbers in the PDF viewer
	page_style_pos = None			# Position (index) of page numbering style
									# in formatting string
	percent_char_read = False		# Was the previous character read a percent
									# sign (%)?

	# Analyse each character in the formatting string
	for i in range(len(page_format)):
		char = page_format[i]

		# If a percentage character was read, then the following character
		# specifies a formatting style
		if char == '%' and not percent_char_read:
			percent_char_read = True

		# The previous character was a percent sign (%)
		elif percent_char_read:
			# Ignore %%; this is used to write a literal percent sign in the
			# prefix
			if char == '%':
				pass

			# Multiple page numbering formats are not permitted
			elif style is not None:
				raise ValueError('only one page numbering style may be \
specified in the formatting string')

			# Permitted page numbering styles
			elif char in ['D', 'R', 'r', 'A', 'a']:
				style = '/' + char
			else:
				raise ValueError(f'invalid formatting style %{char}')

			# Set the index where the page numbering style was found 
			if style is not None:
				page_style_pos = i-1

			percent_char_read = False

	# Set the prefix to add before each page number
	prefix = page_format[:page_style_pos]

	# Suffixes are not permitted, so the page numbering style must be located
	# at the end of the formatting string; if it isn't, then raise an error
	if page_style_pos is not None and page_style_pos != len(page_format)-2:
		raise ValueError('no suffixes are permitted in the page formatting \
string')

	# Return the page numbering prefix and style
	return(prefix, style)


def process_image(input_filepath, output_filepath,
	quality=jpeg_compression_quality):
	"""Read an image file, convert it to JPEG format and write it to a file.

Parameters:
input_filepath (str): The filepath of the image file to read.
output_filepath (str): The filepath of the converted JPEG image to write.
quality (int): The compression quality of the JPEG image (1=worst, 100=best).
"""
	# Check that the specified JPEG compression quality is between 1 and 100
	if type(quality) is not int or quality not in range(1,101):
		raise ValueError('JPEG compression quality must be an integer between \
1 and 100 (1=worst, 100=best)')

	with Image.open(input_filepath) as image:
		# Obtain the density of the original image
		image_density = (72,72)		# Default density (width, height)
		image_density_unit = 1		# 1 = pixels per inch (ppi)
		try:
			if 'dpi' in image.info:
				image_density = image.info['dpi']
			elif image.format.upper() == 'JPEG':
				image_density = image.info['jfif_density']
				image_density_unit = image.info['jfif_unit']
		except KeyError:
			pass

		# If the original image uses a 1-bit or 8-bit palette, convert it to
		# true-colour RGB format
 		# See <https://pillow.readthedocs.io/en/stable/handbook/concepts.html#concept-modes>
		# for details of image modes
		if image.mode in ['1', 'L', 'P']:
			image = image.convert(mode='RGB')

		# Recompress the image as a JPEG file
		# See <https://pillow.readthedocs.io/en/stable/handbook/image-file-formats.html>
		# for details of options for the image.save method
		image.save(output_filepath, optimize=True,
			quality=jpeg_compression_quality,
			jfif_density=image_density,
			jfif_unit=image_density_unit,
			dpi=image_density,
		)


# ------------
# MAIN PROGRAM
# ------------

# -------------------------------
# Read the command line arguments
# -------------------------------

args = _parse_arguments(sys.argv[1:])
command_filename = os.path.basename(sys.argv[0])
error_message_prefix = f'{command_filename}: error: '

# If the output filename does not have an extension, then add a '.pdf'
# extension to it
pdf_output_filepath = args.output_file[0]
if pdf_output_filepath.find('.') == -1:
	pdf_output_filepath += '.pdf'

# If a JPEG compression quality is specified, check that it is a legal value
# between 1 and 100
if args.quality:
	try:
		jpeg_compression_quality = int(args.quality)
		if jpeg_compression_quality not in range(1,101):
			raise ValueError
	except ValueError:
		print(f'{error_message_prefix}-q/--quality argument must be an '
			+ 'integer value between 1 and 100', file=sys.stderr)
		quit()

# Set the page mode 

# Only one magnification setting should be specified
magnification = None
if args.magnification:
	try:
		if len(args.magnification) > 1:
			raise ValueError
	except ValueError:
		print(f'{error_message_prefix}only one magnification setting can be '
			+ 'specified', file=sys.stderr)
		quit()
	magnification = args.magnification[0]

# Only one page mode setting should be specified
page_mode = img2pdf.PageMode.none
if args.page_mode:
	try:
		if len(args.page_mode) > 1:
			raise ValueError
	except ValueError:
		print(f'{error_message_prefix}only one page mode setting can be '
			+ 'specified', file=sys.stderr)
		quit()
	if args.page_mode[0] == 'UseThumbs':
		page_mode = img2pdf.PageMode.thumbs

# Store document properties in a dictionary
pdf_document_properties = { 'author': '', 'title': '' }
for property_ in pdf_document_properties:
	if getattr(args, property_):
		pdf_document_properties[property_] = getattr(args, property_)

# Set the page formatting style to use for displaying page numbers
page_numbering_prefix = None
page_numbering_style = None
if args.page_numbering:
	try:
		page_numbering_prefix, page_numbering_style = \
			parse_page_number_formatting_string(args.page_numbering[0])
	except ValueError as ex:
		print(f'{error_message_prefix}{ex}')
		quit()

# If the first page to open is specified, check that it is a legal value (i.e.
# a positive integer)
first_page = 1
if args.first_page_number:
	try:
		first_page = int(args.first_page_number)
		if first_page < 1:
			raise ValueError
	except ValueError:
		print(f'{error_message_prefix}--first-page-number argument must be a '
			'positive integer value', file=sys.stderr)
		quit()

# Initialise a formatting string for naming image files to be saved to a
# temporary directory (e.g. page0001)
temp_image_filename_index_length = max(4,len(str(len(args.input_files))))
temp_image_filename_format = ('page{:0' + str(temp_image_filename_index_length)
	+ 'd}')


# -----------------------
# Process the image files
# -----------------------

image_files = []	# List of image files to be combined into a PDF file
# Create a temporary directory to store the new image files
with tempfile.TemporaryDirectory() as temp_dir:
	if DEBUG:
		print('Creating temporary directory {0}...'.format(temp_dir))

	# Open and recompress the image files
	input_file_counter = 1	# Number of image files processed successfully
	for input_file in args.input_files:
		# Open the image file
		try:
			with Image.open(input_file) as image:
				(input_file_name, input_file_extension) = \
					os.path.splitext(os.path.basename(input_file))

				output_file = os.path.join(temp_dir,
					temp_image_filename_format.format(input_file_counter)
					+ '.jpg')
				if DEBUG:
					print(f'Processing {input_file} and saving as \
{output_file}...')
				else:
					print(f'Processing {input_file}...')
				process_image(input_file, output_file,
					quality=jpeg_compression_quality)

				# If the original image is a JPEG file and forced compression
				# is not set, compare the sizes of the original and
				# recompressed images; if the original image file is smaller or
				# the same size (in bytes) as the recompressed image, then use
				# the original image in the PDF file
				if (image.format.upper() == 'JPEG' and
					recompress_all_jpegs is False and
					os.path.getsize(input_file) <=
						os.path.getsize(output_file)):
					image_files.append(input_file)
				# Otherwise, use the recompressed image
				else:
					image_files.append(output_file)
						
				input_file_counter += 1

		# The specified image file does not exist
		except FileNotFoundError:
			print(f'Unable to open {input_file}.', file=sys.stderr)

		# Pillow cannot identify the file as an image
		except PIL.UnidentifiedImageError:
			print(f'{input_file} is either not an image file or the file '
				+ 'is corrupted, so it will not be added to the PDF file.',
				file=sys.stderr)

	if image_files:
		# Combine the images into a PDF file
		#
		# Go to https://gitlab.mister-muffin.de/josch/img2pdf/src/branch/main/src/img2pdf.py
		# and search for 'def convert' for a full list of options
		#
		# Using viewer_magnification=img2pdf.Magnification.fit (or similar
		# values) produces an error when PDFs are opened with Adobe Acrobat
		# Reader DC, if using the 'pikepdf' engine; there are no problems when
		# using the 'internal' engine
		#
		# Other options:
		# * viewer_fit_window=True - when PDF is opened, the page will be displayed
		#   so the entire page fits the viewer window
		# * viewer_panes=img2pdf.PageMode.thumbs - show thumbnails as well as the
		#   page; replace with 'outlines' to view bookmarks, or 'none'
		if DEBUG:
			print('The following files will be combined into a PDF file:')
			for file in image_files:
				print(file)

		pdf_data = img2pdf.convert(image_files,
			engine=img2pdf.Engine.pikepdf,
			author=pdf_document_properties['author'],
			title=pdf_document_properties['title'],
			viewer_panes=page_mode,
		)

	else:
		print('No image files were processed successfully, so no PDF file '
			+ 'will be generated.')
		quit()


# ---------------------------------------------
# Perform additional processing on the PDF file
# ---------------------------------------------

# Convert the generated PDF file to a pikepdf object
pdf = pikepdf.open(BytesIO(pdf_data))

page_to_open = 0	# The first page of the PDF file has an index of 0
page_to_open_width = pdf.pages[page_to_open]['/MediaBox'][2]
page_to_open_height = pdf.pages[page_to_open]['/MediaBox'][3]

# Set the number of the first page (see section 7.3.1 of the Adobe PDF v1.3
# Reference)

# /S sets the page numbering style
# /St sets the number of the first page that uses the specified style
page_label = {}
if page_numbering_prefix:
	page_label['/P'] = page_numbering_prefix
if page_numbering_style:
	page_label['/S'] = pikepdf.Name(page_numbering_style)
if first_page > 1:
	page_label['/St'] = first_page
pdf.Root['/PageLabels'] = { '/Nums': [ 0, page_label] }

# Set the magnification and page to open when opening the PDF file; this is
# stored in the OpenAction entry in the document root (see section 3.6.1 of the
# Adobe PDF v1.3 Reference)
#
# There are some bugs in the way img2pdf sets the magnification, so it is set
# using pikepdf instead
if magnification:
	magnification_name = pikepdf.Name('/' + magnification)

	# Define the array containing the destination page details (see table 7.2
	# of the Adobe PDF v1.3 Reference)
	openaction_array = [page_to_open, magnification_name]

	# The FitH magnification needs to specify the vertical coordinate of the
	# top of the page, which is equivalent to its height in PDF units
	if magnification == 'FitH':
		openaction_array.append(page_to_open_height)

	# The FitV magnification needs to specify the horizontal coordinate of the
	# left of the page (i.e. 0)
	elif magnification == 'FitV':
		openaction_array.append(0)

	# Define the magnification
	pdf.Root['/OpenAction'] = openaction_array

# Write the PDF file
try:
	print(f'Writing {pdf_output_filepath}...')
	pdf.save(pdf_output_filepath)
except PermissionError:
	print(f'Unable to write {pdf_output_filepath}!', file=sys.stderr)
	quit()
