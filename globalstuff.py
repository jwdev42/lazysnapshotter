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

config_backups = Path('/etc/lazysnapshotter/backups.conf')
logfile = Path('/var/log/lazysnapshotter.log')
loglevel = logging.DEBUG
mountdir = Path('/run/lazysnapshotter')
status = EXIT_SUCCESS

default_snapshots = 2
max_snapshots = 255

def printException(e: Exception, trace = False):
	if trace:
		traceback.print_exc(file = sys.stderr)
	else:
		if hasattr(e, 'message'):
			print('{}: {}'.format(type(e).__name__, e.message), file = sys.stderr)
		else:
			print(e, file = sys.stderr)

class Bug(Exception):
	pass

class MountPointError(Exception):
	def __init__(self, mountpoint):
		self.message = '"{}" is expected to be a mount point!'.format(str(mountpoint))
		
class DirectoryExpectedError(Exception):
	"""Raised if a function expects a directory, but the corresponding argument is something else."""
	def __init__(self, path):
		self.message = '"{}" is expected to be a directory!'.format(str(path))

class DuplicateSnapshotError(Exception):
	"""Raised if a Snapshot is being added to an already occupied Snapshot slot in the corresponding SnapshotDir."""
	def __init__(self, Snapshot):
		self.message = 'Snapshot "' + Snapshot + '" was attempted to be added twice, that is forbidden!'

class SnapshotDirDoesNotMatchError(Exception):
	"""Raised if a Snapshot from a differrent SnapshotDir is being added to another SnapshotDir."""

class RelativePathNotSupportedError(Exception):
	"""Raised if a relative file path was committed to a function that only supports absolute paths."""

class PathDoesNotExistError(Exception):
	"""Raised if a file path does not exist on the file system."""
	def __init__(self, path):
		self.message = 'Path "' + str(path) + '" does not exist on the file system!'

class PathIsNoMountpointError(Exception):
	"""Raised if a file path is not a mount point."""
	def __init__(self, path):
		self.message = 'Path "' + str(path) + '" is not a mount point!'

class CryptDeviceStillMountedError(Exception):
	"""Raised if a crypt device that is still mounted was attempted to be closed."""
