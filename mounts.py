#!/usr/bin/env python

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


import os
import subprocess
import shutil
import json

import globalstuff
import verify

from uuid import UUID
from pathlib import Path

_mounts_file = '/proc/mounts'

def readmounts():
	m = open(_mounts_file, 'r')
	l = m.readline()
	mounts = list()
	while l is not '':
		mounts.append(l.split())
		l = m.readline()
	return mounts

def deviceMountPoints(dev):
	"""Counts how many active mount points exist for device dev."""
	mounts = readmounts()
	i = 0
	for l in mounts:
		if l[0] == dev:
			i = i + 1
	return i

def isMountPoint(path):
	"""Returns true if path is an active mount point."""
	mounts = readmounts()
	for l in mounts:
		if l[1] == path:
			return True
	return False

def getBlockDeviceFromUUID(block_uuid: UUID):
	workdir = Path(os.getcwd())
	temp_workdir = Path('/dev/disk/by-uuid/')
	os.chdir(temp_workdir)
	symlink = Path(str(block_uuid))
	verify.requireRelativePath(symlink)
	if not symlink.exists():
		raise globalstuff.PathDoesNotExistError(symlink)
	resolved_path = Path(os.readlink(symlink))
	resolved_path = resolved_path.resolve(True)
	os.chdir(workdir)
	return resolved_path

def isLuks(path):
	command = [ shutil.which('cryptsetup'), 'isLuks', str(path) ]
	res = subprocess.run(command)
	if res.returncode == 0:
		return True
	elif res.returncode == 1:
		return False
	else:
		res.check_returncode()
	
def getLuksMapping(luks_dev):
	command = [ shutil.which('lsblk'), '-J', '-p', str(luks_dev) ]
	res = subprocess.run(command, stdout=subprocess.PIPE)
	res.check_returncode()
	data = json.loads(bytes.decode(res.stdout))
	for e in data['blockdevices']:
		if e['name'] == str(luks_dev):
			if 'children' in e:
				for c in e['children']:
					if c['type'] == 'crypt':
						return c['name']
	return None

def getMountpoint(dev):
	command = [ shutil.which('lsblk'), '-J', '-p', str(dev) ]
	res = subprocess.run(command, stdout=subprocess.PIPE)
	res.check_returncode()
	data = json.loads(bytes.decode(res.stdout))
	for e in data['blockdevices']:
		if e['name'] == str(dev):
			return e['mountpoint']
	return None
