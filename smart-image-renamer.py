#! /usr/bin/env python

# smart-image-renamer
#
# Author: Ronak Gandhi (ronak.gandhi@ronakg.com)
# Project Home Page: https://github.com/ronakg/smart-image-renamer
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import argparse
import itertools
import os
import re

from PIL import Image
from PIL.ExifTags import TAGS


class NotAnImageFile(Exception):
    """This file is not an Image"""
    pass


class InvalidExifData(Exception):
    """Could not find any EXIF or corrupted EXIF"""
    pass


def get_cmd_args():
    """Get, process and return command line arguments to the script
    """
    help_description = '''
Smart Image Renamer

Rename your photos in bulk using information stored in EXIF.
'''

    help_epilog = '''
Format string for the file name is defined by a mix of custom text and following tags enclosed in {}:
  YYYY        Year
  MM          Month
  DD          Day
  hh          Hours
  mm          Minutes
  ss          Seconds
  Seq         Sequence number
  Artist      Artist
  Make        Camera Make
  Model       Camera Model
  Folder      Parent folder of the image file

Examples:
  Format String:          {YYYY}-{MM}-{DD}-{Folder}-{Seq}
  File Name:              2014-05-09-Wedding_Shoot-001.JPEG
                          2014-05-09-Wedding_Shoot-002.JPEG

  Format String:          {YYYY}{DD}{MM}_{Model}_Beach_Shoot_{Seq}
  File Name:              20140429_PENTAX K-x_Beach_Shoot_001.JPEG
                          20140429_PENTAX K-x_Beach_Shoot_002.JPEG
    '''

    parser = argparse.ArgumentParser(description=help_description,
                                     formatter_class=argparse.RawTextHelpFormatter,
                                     epilog=help_epilog)
    parser.add_argument('-f', dest='format', required=True, type=str,
                        help='Format of the new file name')
    parser.add_argument('-s', dest='sequence', type=int, default=1,
                        help='Starting sequence number (default: 1)')
    parser.add_argument('-r', dest='recursive', default=False,
                        action='store_true',
                        help='Recursive mode')
    parser.add_argument('-i', dest='hidden', default=False,
                        action='store_true', help='Include hidden files')
    parser.add_argument('-t', dest='test', default=False, action='store_true',
                        help='Test mode. Don\'t apply changes.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument("-v", "--verbose", action="store_true")
    group.add_argument("-q", "--quiet", action="store_true")
    parser.add_argument('input', nargs='+',
                        help='Absolute path to file or directory')

    return parser.parse_args()


def get_exif_data(img_file):
    """Read EXIF data from the image.

    img_file: Absolute path to the image file

    Returns: A dictionary containing EXIF data of the file

    Raises: NotAnImageFile if file is not an image
            InvalidExifData if EXIF can't be processed
    """
    with open(img_file, 'rb') as fp:
        try:
            img = Image.open(fp)
        except (OSError, IOError):
            raise NotAnImageFile

        try:
            # Use TAGS module to make EXIF data human readable
            exif_data = {
                TAGS[k]: v
                for k, v in img._getexif().items()
                if k in TAGS
            }
        except AttributeError:
            raise InvalidExifData

        # Add image format to EXIF
        exif_data['format'] = img.format
        return exif_data

if __name__ == '__main__':
    skipped_files = []
    args = get_cmd_args()

    input_paths = [os.path.abspath(input) for input in args.input]
    input_format = args.format
    verbose = args.verbose
    quiet = args.quiet
    sequence_start = args.sequence
    test_mode = args.test
    recursive = args.recursive
    include_hidden = args.hidden

    for input_path in input_paths:
        for root, dirs, files in os.walk(input_path):
            # Skip hidden directories unless specified by user 
            if not include_hidden and os.path.basename(root).startswith('.'):
                continue

            # Initialize sequence counter
            # Use no of files to determine padding for sequence numbers
            seq = itertools.count(start=sequence_start)
            seq_width = len(str(len(files)))

            print('Processing folder: {}'.format(root))
            for f in sorted(files):
                # Skip hidden files unless specified by user 
                if not include_hidden and f.startswith('.'):
                    continue

                old_file_name = os.path.join(root, f)
                try:
                    # Get EXIF data from the image
                    exif_data = get_exif_data(old_file_name)
                except NotAnImageFile:
                    continue
                except InvalidExifData:
                    skipped_files.append(old_file_name)
                    continue

                # Find out the original timestamp or digitized timestamp from the EXIF
                img_timestamp = (exif_data.get('DateTimeOriginal') or
                                 exif_data.get('DateTimeDigitized'))

                if not img_timestamp:
                    skipped_files.append(old_file_name)
                    continue

                # Extract year, month, day, hours, minutes, seconds from timestamp
                img_timestamp =\
                    re.search(r'(?P<YYYY>\d\d\d?\d?):(?P<MM>\d\d?):(?P<DD>\d\d?) '
                              '(?P<hh>\d\d?):(?P<mm>\d\d?):(?P<ss>\d\d?)',
                              img_timestamp.strip())

                if not img_timestamp:
                    skipped_files.append(old_file_name)
                    continue

                # Generate data to be replaced in user provided format
                new_image_data = {'Artist': exif_data.get('Artist', ''),
                                  'Make': exif_data.get('Make', ''),
                                  'Model': exif_data.get('Model', ''),
                                  'Folder': os.path.basename(root),
                                  'Seq': '{0:0{1}d}'.format(next(seq), seq_width),
                                  'ext': exif_data.get('format', '')
                                  }
                new_image_data.update(img_timestamp.groupdict())

                # Generate new file name according to user provided format
                new_file_name = (input_format + '.{ext}').format(**new_image_data)
                new_file_name_complete = os.path.join(root, new_file_name)

                # Don't rename files if we are running in test mode
                if not test_mode:
                    try:
                        os.rename(old_file_name, new_file_name_complete)
                    except OSError:
                        skipped_files.append(old_file_name)
                        continue

                if verbose:
                    print('{0} --> {1}'.format(old_file_name,
                                             new_file_name_complete))
                elif not quiet:
                    print('{0} --> {1}'.format(f, new_file_name))

            # Folder processed
            print('')

            # Break if recursive flag is not present
            if not recursive:
                break

    # Print skipped files
    if skipped_files and not quiet:
        print('\nSkipped Files:\n\t' + '\n\t'.join(skipped_files))
