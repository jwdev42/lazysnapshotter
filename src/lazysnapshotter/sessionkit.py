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

import copy
import logging
import os
import os.path
import uuid

from . import globalstuff
from . import verify

from pathlib import Path

logger = logging.getLogger(__name__)

class BackupJob:
	
	def __init__(self, jobfile: Path):
		self.jobfile = jobfile

	def register(self, pid, configfile, identifier):
		pass
		
class RuntimePathManager:
	
	dir_keys = ( 'mounts', 'pid' )
	file_keys = ( 'jobs', 'pidfile' )
	
	def __init__(self, rundir: Path):
		verify.requireAbsolutePath(rundir)
		self.rootdir = rundir
	
	def getDirectory(self, key, create = False) -> Path:
		directory = None
		if key == 'mounts':
			directory = self.rootdir / Path('mounts')
		elif key == 'pid':
			directory = self.rootdir / Path('pid')
		else:
			raise globalstuff.Bug('"{}" is an invalid key.'.format(key))
		if create == True and not directory.exists():
			directory.mkdir(parents = True)
		return directory
		
	def getFile(self, key, create_dir = False) -> Path:
		fp = None
		if key == 'jobs':
			fp = self.rootdir / Path('jobs')
		elif key == 'pidfile':
			d = self.getDirectory('pid', create_dir)
			fp = d / Path('{}.pid'.format(str(os.getpid())))
		else:
			raise globalstuff.Bug('"{}" is an invalid key.'.format(key))
		return fp
		
class Session:
	
	def __init__(self, rundir: Path):
		self.rpm = RuntimePathManager(rundir)
		self.custom_mountdir = None
		self.session_id = uuid.uuid4()
	
	def setup(self):
		self.pidfile = self.rpm.getFile('pidfile', create_dir = True)
		logger.debug('Creating pidfile "%s"', str(self.pidfile))
		fp = open(self.pidfile, 'w')
		fp.close()
	
	def cleanup(self):
		if hasattr(self, 'pidfile'):
			logger.debug('Deleting pidfile "%s"', str(self.pidfile))
			if self.pidfile.exists():
				self.pidfile.unlink()
	
	def customizeMountDir(self, mountdir: Path):
		verify.requireAbsolutePath(mountdir)
		self.custom_mountdir = copy.deepcopy(mountdir)
	def getMountDir(self, create_parent = False):
		if self.custom_mountdir is None:
			mounts = self.rpm.getDirectory('mounts', create_parent)
			mountdir = mounts / Path(str(self.session_id))
			return mountdir
		else:
			return copy.deepcopy(self.custom_mountdir)
		
	
	
