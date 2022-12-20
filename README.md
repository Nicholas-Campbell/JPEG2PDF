# JPEG2PDF

A Python script to convert image files to JPEG format and combine them into a PDF file.

This script uses the [img2pdf](https://pypi.org/project/img2pdf/) package by Johannes Schauer Marin Rodrigues. img2pdf is also capable of generating PDF files from images, but JPEG2PDF provides some additional functionality, such as:

* Specifying and formatting page numbers
* Specifying the compression quality when images are (re)compressed to JPEG format

# Usage

Below is the help message displayed by JPEG2PDF when the `-h` or `-?` arguments are used.

```
usage: jpeg2pdf.py [-o output_file] [-h] [-a name] [-t title] [-q quality]
                   [--fit-horizontal] [--fit-vertical] [--fit-window]
                   [--show-thumbnails] [-p format_string]
                   [--first-page-number page]
                   input_file [input_file ...]

file arguments:
  input_file            image files to be added to the PDF document
  -o output_file, --output-file output_file
                        the PDF file to write

optional arguments:
  -h, --help, -?        show this help message and exit
  -a name, --author name
                        set the author of the PDF document
  -t title, --title title
                        set the title of the PDF document

JPEG compression settings (optional):
  These settings control the compression of images when they are being
  converted to JPEG format.

  -q quality, --quality quality
                        set the compression quality when (re)compressing
                        images (1=worst, 100=best); the default is 75

viewer settings (optional):
  These settings control how the PDF file is displayed when it is opened in
  a PDF viewer.

  --fit-horizontal      fit the page to the width of the window
  --fit-vertical        fit the page to the height of the window
  --fit-window          fit the entire page within the window
  --show-thumbnails     show thumbnails for each page

page numbering settings (optional):
  These settings control how the pages of the PDF file are numbered and
  displayed.

  -p format_string, --page-numbering format_string
                        set the formatting of page numbers (e.g. %D for Arabic
                        numerals (1, 2, 3...), %r for lower case Roman
                        numerals (i, ii, iii...), %A for upper case letters
                        (A, B, C...))
  --first-page-number page
                        set the number of the first page of the PDF file
```
 
# Licence

JPEG2PDF is licensed under the MIT License, which can be found in the LICENSE file.

img2pdf is licensed under the GNU Lesser General Public License (LGPL) v3.0.
