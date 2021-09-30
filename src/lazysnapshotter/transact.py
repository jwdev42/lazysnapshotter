#!/usr/bin/env python

#lazysnapshotter - a backup tool using btrfs
#Copyright (C) 2021 Joerg Walter
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

import btrfsutil
import logging
import os
from dataclasses import dataclass
from uuid import UUID
from pathlib import Path
from enum import Enum
from os.path import isdir
from .verify import requireAbsolutePath

logger = logging.getLogger(__name__)

class State(Enum):
	UNPREPARED = 1
	PREPARED = 2
	PRELIM_SNAPSHOT = 3
	SENT = 4
	FINISHED = 5
	UNDONE = 6

class SnapshotType(Enum):
	SRC = 1
	DST = 2

class TransactionError(Exception):
	pass



@dataclass
class Transact:
	id: UUID
	snapshot_dir: Path
	backup_dir: Path
	source: Path
	_state = State.UNPREPARED
	_snapshots = dict() #track created snapshots for rollback
	
	def _src_prelim_snapshot(self):
		return self.snapshot_dir.joinpath(str(self.id))
		
	def _dst_prelim_snapshot(self):
		return self.backup_dir.joinpath(str(self.id))
	
	def _must_state(self, state):
		if self._state != state:
			raise TransactionError(f'Expected state {state}, got state {self._state}')
	
	def prepare(self, mkdirs: bool):
		def prepare_dir(directory: Path, name: str):
			requireAbsolutePath(directory, '{} directory must be an absolute path')
			if not isdir(directory) and mkdirs:
				os.mkdir(directory, mode=0o755)
			if not isdir(directory):
				raise TransactionError('{} directory not found'.format(name))
		
		self._must_state(State.UNPREPARED)
		
		prepare_dir(self.snapshot_dir, 'Snapshot')
		prepare_dir(self.backup_dir, 'Backup')
		requireAbsolutePath(self.source, 'Backup source must be an absolute path')
		self._state = State.PREPARED
	
	def create_prelim_snapshot(self):
		self._must_state(State.PREPARED)
		btrfsutil.create_snapshot(self.source, self._src_prelim_snapshot(), read_only = True)
		self._snapshots[SnapshotType.SRC] = self._src_prelim_snapshot()
		self._state = State.PRELIM_SNAPSHOT
	
	def send(self, parent: Path, send_func):
		self._must_state(State.PRELIM_SNAPSHOT)
		try:
			send_func(self._src_prelim_snapshot(), self.backup_dir, parent)
		except Exception as e:
			raise(e)
		finally:
			if isdir(self._dst_prelim_snapshot()):
				logger.debug('Received preliminary snapshot on the backup drive: {}'.format(str(self._dst_prelim_snapshot())))
				self._snapshots[SnapshotType.DST] = self._dst_prelim_snapshot()
			else:
				raise TransactionError('Preliminary snapshot should have been created on the backup drive, but wasn\'t')
		self._state = State.SENT
	
	def rename(self, name: str):
		def rename_snapshot(key: str, src, dst):
			logger.debug('Renaming preliminary snapshot "{}" to "{}"'.format(str(src), str(dst)))
			os.rename(src, dst)
			self._snapshots[key] = dst
		self._must_state(State.SENT)
		rename_snapshot(SnapshotType.SRC, self._src_prelim_snapshot(), self.snapshot_dir.joinpath(name))
		rename_snapshot(SnapshotType.DST, self._dst_prelim_snapshot(), self.backup_dir.joinpath(name))
		self._state = State.FINISHED

	def rollback(self):
		for v in self._snapshots.values():
			logger.debug('Rollback: Deleting snapshot "{}"'.format(str(v)))
			btrfsutil.delete_subvolume(v)
		self._state = State.UNDONE
	
