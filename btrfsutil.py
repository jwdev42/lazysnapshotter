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


import logging
import subprocess
import datetime
import os
import copy

import globalstuff
import verify

from pathlib import Path

logger = logging.getLogger(__name__)

class SnapshotDir:
	def __init__(self, path: Path, keep = globalstuff.default_snapshots):
		if not isinstance(path, Path) or not path.is_dir() or not path.is_absolute():
			raise globalstuff.Bug('Path error while creating SnapshotDir object')
		if not verify.snapshot_count(keep):
			raise globalstuff.Bug('Attempted to create a SnapshotDir object with an out-of-range snapshot count!')
		self._folder = path
		self._snapshots = list()
		self._keep = keep
		self._scanned = False
		
	def _addSnapshot(self, snapshot: 'btrfsutil.Snapshot'):
		if snapshot.getSnapshotDir() is not self:
			raise globalstuff.Bug
		for existing in self._snapshots:
			if existing < snapshot: #snapshot is newer
				logger.debug('Snapshot "%s" is newer than Snapshot "%s", will continue.', \
				str(snapshot), str(existing))
				continue
			elif existing > snapshot: #snapshot is older
				logger.debug('Snapshot "%s" will be inserted before Snapshot "%s".', \
				str(snapshot), str(existing))
				i = self._snapshots.index(existing)
				self._snapshots.insert(i, snapshot)
				return
			elif existing == snapshot:
				raise globalstuff.Bug('Duplicate Snapshot!')
		
		if logger.getEffectiveLevel() == logging.DEBUG:
			if len(self._snapshots) == 0:
				logger.debug('Snapshot "%s" will be inserted as first element.', str(snapshot))
			else:
				logger.debug('Snapshot "%s" will be inserted after "%s".', str(snapshot), str(self._snapshots[-1]))
		
		self._snapshots.append(snapshot)
	
	def getPath(self):
		return copy.deepcopy(self._folder)
	
	def scan(self):
		"""Scans the directory for Snapshots and adds them to the internal data structure."""
		if self._scanned:
			self._snapshots = list()
			logger.debug('Rescanning snapshot directory "%s"', str(self.getPath()))
		else:
			logger.debug('Started scan of snapshot directory "%s"', str(self.getPath()))
		for f in self._folder.iterdir():
			if f.is_dir() and isSnapshotName(str(f.name)):
				s = FileNameSnapshot(self, str(f.name))
				self._addSnapshot(s)
		self._scanned = True
	
	def createSnapshot(self, source: Path) -> 'btrfsutil.Snapshot':
		verify.requireAbsolutePath(source)
		today = datetime.date.today()
		indexmm = 0
		for s in self._snapshots:
			if s.getYear() == today.year and \
			s.getMonth() == today.month and \
			s.getDay() == today.day and \
			s.getIndex() > indexmm:
				indexmm = s.getIndex()
		index = indexmm + 1
		fname = '{}-{}-{}.{}'.format(today.year, today.month, today.day, index)
		s = Snapshot(self, fname, today.year, today.month, today.day, index)
		s.create(source)
		self._addSnapshot(s)
		return s
		#refactoringmarker
	def purgeSnapshots(self):
		for s in self._snapshots[:]:
			if len(self._snapshots) > self._keep:
				logger.debug('Removing Snapshot "%s" from "%s"', str(s), str(s.getSnapshotPath()))
				s.delete()
				self._snapshots.remove(s)
			else:
				break
	
	def getNewestSnapshot(self) -> 'btrfsutil.Snapshot':
		if len(self._snapshots) < 1:
			return None
		else:
			return self._snapshots[-1]
	
	def printSnapshots(self):
		for s in self._snapshots:
			print(s)

class Snapshot:
	def __init__(self, snapshot_dir: SnapshotDir, name_on_filesystem: str, year: int, month: int, day: int, index: int = 1):
		if not isinstance(snapshot_dir, SnapshotDir):
			raise TypeError('arg 1 must be of SnapshotDir!')
		if index < 1:
			raise ValueError('index must be 1 or greater!')
		self._ssdir = snapshot_dir
		self._name_on_filesystem = name_on_filesystem
		self._year = year
		self._month = month
		self._day = day
		self._index = index
		
	def __str__(self):
		return copy.deepcopy(self._name_on_filesystem)
		
	def getYear(self):
		return copy.deepcopy(self._year)
	
	def getMonth(self):
		return copy.deepcopy(self._month)
		
	def getDay(self):
		return copy.deepcopy(self._day)
	
	def getIndex(self):
		return copy.deepcopy(self._index)
	
	def getSnapshotDir(self) -> SnapshotDir:
		return self._ssdir
		
	def getSnapshotPath(self) -> Path:
		return self.getSnapshotDir().getPath() / Path(self._name_on_filesystem)
	
	def existsOnFilesystem(self):
		return self.getSnapshotPath().exists()
	
	def __lt__(self, other):
		if self._year < other._year and \
		self._month < other._month  and \
		self._day < other._day  and \
		self._index < other._index:
			return True
		return False
	
	def __gt__(self, other):
		if self._year > other._year and \
		self._month > other._month and \
		self._day > other._day and \
		self._index > other._index:
			return True
		return False
	
	def __eq__(self, other):
		if self._year == other._year and \
		self._month == other._month and \
		self._day == other._day and \
		self._index == other._index:
			return True
		return False
	
	def create(self, source: Path):
		if self.existsOnFilesystem():
			raise globalstuff.Bug
		command = [ 'btrfs', 'subvolume', 'snapshot', '-r', str(source), str(self.getSnapshotPath()) ]
		res = subprocess.run(command)
		res.check_returncode()
	
	def delete(self):
		if not self.existsOnFilesystem():
			raise globalstuff.Bug
		command = [ 'btrfs', 'subvolume', 'delete', str(self.getSnapshotPath()) ]
		res = subprocess.run(command)
		res.check_returncode()

class FileNameSnapshot(Snapshot):
	
	def __init__(self, snapshot_dir: SnapshotDir, name_on_filesystem: str):
		if not isSnapshotName(name_on_filesystem):
			raise globalstuff.Bug()
		
		temp1 = name_on_filesystem.split('.')
		temp2 = temp1[0].split('-')
		
		year = int(temp2[0])
		month = int(temp2[1])
		day = int(temp2[2])
		index = int(temp1[1])
		super().__init__(snapshot_dir, name_on_filesystem, year, month, day, index)

def isSnapshotName(name):
	l = name.split('.')
	if len(l) is not 2:
		return False
	if not verify.isodate(l[0]):
		return False
	if not verify.snapshot_revision(l[1]):
		return False
	return True


