#!/usr/bin/env python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2020 Joerg Walter
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


import re
from pathlib import Path

from . import globalstuff

_regexes = dict()
_regexes['backup_id'] = re.compile('^(\w|\d)(\w|\d|-)*$')
_regexes['uuid'] = re.compile('^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$')
_regexes['isodate'] = re.compile('^(000[1-9]|00[1-9][0-9]|0[1-9][0-9]{2}|[1-9][0-9]{3})-(0[1-9]|1[0-2])-(0[1-9]|[12][0-9]|3[01])$')
_regexes['snapshot_revision'] = re.compile('^[1-9][0-9]*$')

LOGLEVELS = ( 'CRITICAL', 'ERROR', 'WARNING', 'INFO', 'DEBUG' )

def backup_id(backup_id: str):
	return _regexes['backup_id'].fullmatch(backup_id) is not None and backup_id.upper() != 'DEFAULT'

def uuid(uuid: str):
	return _regexes['uuid'].fullmatch(uuid) is not None

def isodate(datestring: str):
	return _regexes['isodate'].fullmatch(datestring) is not None

def snapshot_revision(rev: str):
	return _regexes['snapshot_revision'].fullmatch(rev) is not None

def snapshot_count(c: int):
	if not isinstance(c, int):
		raise TypeError('{}: arg 1 must be of int'.format(snapshot_count.__name__))
	return 0 < c <= globalstuff.max_snapshots

def requireAbsolutePath(path, errmsg = None):
	if not isinstance(path, Path):
		raise TypeError('arg 1 must be of pathlib.Path')
	if not path.is_absolute():
		if errmsg is not None:
			raise VerificationError(errmsg)
		else:
			raise VerificationError('"{}" is not an absolute Path!'.format(str(path)))
		
def requireRelativePath(path, errmsg = None):
	if not isinstance(path, Path):
		raise TypeError('arg 1 must be of pathlib.Path')
	if path.is_absolute():
		if errmsg is not None:
			raise VerificationError(errmsg)
		else:
			raise VerificationError('"{}" is not a relative path!'.format(str(path)))

def requireExistingPath(path, errmsg = None):
	if not isinstance(path, Path):
		raise TypeError('arg 1 must be of pathlib.Path')
	if not path.exists():
		if errmsg is not None:
			raise VerificationError(errmsg)
		else:
			raise VerificationError('Path "{}" does not exist in the file system!'.format(str(path)))

def requireRightAmountOfSnapshots(snapshots: int):
	if not isinstance(snapshots, int):
		raise TypeError('arg 1 must be of int')
	if not snapshot_count(snapshots):
		raise VerificationError('{} is an invalid amount of snapshots!'.format(snapshots))

class VerificationError(Exception):
	"""Thrown if a require* function cannot verify its condition."""
	pass
