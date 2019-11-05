#!/usr/bin/python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2019  Joerg Walter
#
#This program is free software: you can redistribute it and/or modify
#it under the terms of the GNU General Public License as published by
#the Free Software Foundation, version 3 of the License.
#
#This program is distributed in the hope that it will be useful,
#but WITHOUT ANY WARRANTY; without even the implied warranty of
#MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License
#along with this program.  If not, see https://www.gnu.org/licenses.


import logging
import traceback
import sys
from pathlib import Path

#Exit Codes:
EXIT_SUCCESS = 0 #normal program exit
EXIT_FAILURE = 1 #generic error
EXIT_COMMANDLINE = 2 #Error while processing the command line arguments
EXIT_BUG = 23 #a bug was triggered

config_backups = Path('/etc/lazysnapshotter/backups.conf')
logfile = Path('/var/log/lazysnapshotter.log')
logfile_from_cmdline = False
loglevel = logging.INFO
loglevel_from_cmdline = False
mountdir = Path('/run/lazysnapshotter')
status = EXIT_SUCCESS
debug_mode = False
default_snapshots = 2
max_snapshots = 255

def printException(e: Exception, trace = False):
	if trace or debug_mode:
		traceback.print_exc(file = sys.stderr)
	else:
		print('{}: {}'.format(type(e).__name__, e), file = sys.stderr)



class Bug(Exception):
	def __init__(self, msg = None):
		status = EXIT_BUG
		if msg is not None:
			super().__init__(msg)

class ApplicationError(Exception):
	"""Generic Exception raised by code in this app."""
	pass
