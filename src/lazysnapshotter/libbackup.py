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

import btrfsutil
import logging
import subprocess
import shutil
import os
import os.path
import copy
import warnings
from pathlib import Path
from time import sleep

from . import globalstuff
from . import verify
from . import mounts
from . import snapshotkit

logger = logging.getLogger(__name__)

class BackupEntry:
	def __init__(self, name: str):
		self._name = name
		self._sourceSubvolume = None #the subvolume to backup
		self._sourceSnapshotDir = None
		self._targetDevice = None #the device to backup to
		self._backupDir = None #relative path on the backup device to its snapshots
		self._targetSnapshotDir = None #SnapshotDir object created from the full joint path of targetDevice and backupDir
		self._snapshots = None #Define a custom amount of snapshots to keep
	#setters:
	def setSourceSubvolume(self, path: Path):
		"""Sets the btrfs subvolume to backup"""
		verify.requireAbsolutePath(path)
		verify.requireExistingPath(path)
		self._sourceSubvolume = path
	
	def setSourceSnapshotDir(self, ss_dir: Path):
		"""Sets the directory containing the snapshots on the source medium."""
		verify.requireAbsolutePath(ss_dir)
		verify.requireExistingPath(ss_dir)
		if self._snapshots is not None:
			self._sourceSnapshotDir = snapshotkit.SnapshotDir(ss_dir, keep = self._snapshots)
		else:
			self._sourceSnapshotDir = snapshotkit.SnapshotDir(ss_dir)
	
	def setTargetDevice(self, path: Path):
		"""Sets the passed block device as the unencrypted target partition on the backup medium."""
		verify.requireAbsolutePath(path)
		verify.requireExistingPath(path)
		self._targetDevice = path
		
	def setTargetUUID(self, target_uuid):
		"""like setTargetDevice, but takes the device's UUID."""
		dev = mounts.getBlockDeviceFromUUID(target_uuid)
		self.setTargetDevice(dev)
		
	def setBackupDir(self, path: Path):
		"""The passed argument must be the relative path to the snapshots on the backup medium."""
		verify.requireRelativePath(path)
		self._backupDir = path
		
	def setTargetSnapshotDir(self, tss_dir: Path):
		verify.requireAbsolutePath(tss_dir)
		verify.requireExistingPath(tss_dir)
		if self._snapshots is not None:
			self._targetSnapshotDir = snapshotkit.SnapshotDir(tss_dir, self._snapshots)
		else:
			self._targetSnapshotDir = snapshotkit.SnapshotDir(tss_dir)
	
	def setSnapshots(self, snapshots: int):
		if self._sourceSnapshotDir is not None or self._targetSnapshotDir is not None:
			warnings.warn('setSnapshots called after setSourceSnapshotDir or setTargetSnapshotDir will have no effect!')
		verify.requireRightAmountOfSnapshots(snapshots)
		self._snapshots = snapshots
		
	#getters:
	def getName(self):
		return copy.deepcopy(self._name)
	
	def getSourceSubvolume(self):
		return copy.deepcopy(self._sourceSubvolume)
	
	def getSourceSnapshotDir(self):
		return self._sourceSnapshotDir
	
	def getTargetDevice(self):
		return copy.deepcopy(self._targetDevice)
		
	def getBackupDir(self):
		return copy.deepcopy(self._backupDir)
		
	def getTargetSnapshotDir(self):
		return self._targetSnapshotDir
	
	def getSnapshots(self):
		return copy.deepcopy(self._snapshots)

class Backup:
	def __init__(self, entry: BackupEntry):
		if not isinstance(entry, BackupEntry):
			raise TypeError('arg 1 must be of libbackup.BackupEntry')
		self._entry = entry
		self._mountPoint = None
		self._mountPointCreated = False
		self._luksmapping = None
		
	def setMountPoint(self, path):
		verify.requireAbsolutePath(path)
		if not path.is_mount():
			raise globalstuff.ApplicationError('Path "{}" is expected to be a mount point!'.format(path))
		self._mountPoint = path
	
	def setLuksMapping(self, path):
		verify.requireAbsolutePath(path)
		self._luksmapping = path
	
	def getEntry(self):
		return self._entry
	
	def getMountPoint(self):
		return copy.deepcopy(self._mountPoint)
		
	def getLuksMapping(self):
		return copy.deepcopy(self._luksmapping)
	
	def hasLuksMapping(self):
		"""Returns True if a luks mapping has been set. Returns false otherwise."""
		if self._luksmapping is None:
			return False
		else:
			return True
	
	def isMounted(self):
		"""Returns True if the mount()-Method ran successfully and set a mount point. Returns false otherwise."""
		if self._mountPoint is None:
			return False
		else:
			return True
			
	def wasMountPointCreated(self):
		"""Returns True if the mount()-Method created the directory of the mount point, false otherwise."""
		return copy.deepcopy(self._mountPointCreated)
			
	def openLuks(self, keyfile=None):
		"""Opens the LUKS container specified in the BackupEntry, sets the BackupEntry's
		Target Device as a side effect."""
		dev = self._entry.getTargetDevice()
		verify.requireAbsolutePath(dev)
		if keyfile is not None and not isinstance(keyfile, Path):
			raise TypeError('keyfile must be of pathlib.Path')
		name = str(globalstuff.session.session_id)
		command = [ shutil.which('cryptsetup'), 'open', str(dev), name ]
		if keyfile is not None:
			command.append('--key-file')
			command.append(str(keyfile))
		res = subprocess.run(command)
		res.check_returncode()
		p = Path('/dev/mapper/') / Path(name)
		verify.requireExistingPath(p)
		logger.debug('LUKS Container "%s" is open at "%s".', str(dev), str(p))
		self._luksmapping = p
	
	def closeLuks(self):
		if self._luksmapping is None:
			logger.warning('Cannot close LUKS device, no device found!')
			return False
		if self.isMounted():
			logger.warning('Cannot close LUKS device "%s" as it is still mounted!', str(self._luksmapping))
			return False
		verify.requireExistingPath(self._luksmapping)
		command = [ shutil.which('cryptsetup'), 'close', str(self._luksmapping) ]
		res = subprocess.run(command)
		try:
			res.check_returncode()
		except subprocess.CalledProcessError as e:
			globalstuff.printException(e)
			logger.error('Failed to close LUKS container "%s"!', str(self._mountPoint))
			return False
		logger.debug('LUKS Container at "%s" was closed.', str(self._luksmapping))
		self._luksmapping = None
		return True
	
	def mount(self, mountpath: Path):
		verify.requireAbsolutePath(mountpath)
		verify.requireExistingPath(mountpath.parent)
		if not mountpath.exists():
			os.mkdir(mountpath)
			logger.debug('Created mount point "%s".', str(mountpath))
			self._mountPointCreated = True
		dev = None
		if self._luksmapping is not None:
			dev = self._luksmapping
		else:
			dev = self._entry.getTargetDevice()
		verify.requireExistingPath(dev)
		command = [ shutil.which('mount'), str(dev), str(mountpath) ]
		res = subprocess.run(command)
		res.check_returncode()
		self._mountPoint = mountpath
		logger.debug('Device "%s" mounted at "%s".', str(dev), str(self._mountPoint))
	
	def unmount(self, tries = 1, interval = 0):
		if not self.isMounted():
			raise ValueError("unmount cannot be called on a backup object that has no mount point")
		verify.requireExistingPath(self._mountPoint)
		command = [ shutil.which('umount'), str(self._mountPoint) ]
		while tries > 0:
			res = subprocess.run(command)
			if res.returncode == 0:
				logger.debug('"%s" was unmounted.', str(self._mountPoint))
				return True
			elif res.returncode == 32 and tries > 1:
				logger.info('Could not unmount device "%s" as it is busy, will try again in %s seconds for %s times.', str(self._mountPoint), str(interval), str(tries))
				sleep(interval)
			else:
				logger.error('Failed to unmount "%s", umount returned %s!', str(self._mountPoint), str(res.returncode))
				return False
			tries = tries - 1
		return False
	
	def removeMountPoint(self):
		#remove mount point directory if it was created by mount():
		try:
			if self.wasMountPointCreated():
				os.rmdir(self._mountPoint)
		finally:
			self._mountPoint = None
	
	def run(self):
		e = self.getEntry()
		logger.info('Starting Backup.')
		#forward declarations, do not remove:
		source_snapshot = None 
		process_send = None
		process_receive = None
		ssd_backup = None
		try:
			ssd_source = e.getSourceSnapshotDir()
			ssd_source.scan()
			ssd_backup = e.getTargetSnapshotDir()
			ssd_backup.scan()
			common_snapshots = ssd_source.getCommonSnapshots(ssd_backup)
			source_snapshot = ssd_source.createSnapshot(e.getSourceSubvolume())
			send_command = [ shutil.which('btrfs'), 'send' ]
			if len(common_snapshots[0]) > 0:
				#incremental backup
				parent_snapshot = common_snapshots[0][-1]
				if not parent_snapshot < source_snapshot:
					raise BackupError('The parent snapshot must be older than the current snapshot!')
				send_command.append('-p')
				send_command.append(str(parent_snapshot.getSnapshotPath()))
				send_command.append(str(source_snapshot.getSnapshotPath()))
				logger.info('Parent Snapshot: "%s".', str(parent_snapshot.getSnapshotPath()))
			else:
				#full backup
				send_command.append(str(source_snapshot.getSnapshotPath()))
			logger.info('Snapshot: "%s".', str(source_snapshot.getSnapshotPath()))
			logger.info('Target Directory: "%s".', str(ssd_backup.getPath()))
			
			receive_command = [ shutil.which('btrfs'), 'receive', '-e', str(ssd_backup.getPath()) ]
			
			pp = None #forward declaration, do not remove
			try:
				logger.info('Starting transfer to the backup drive.')
				pp = os.pipe()
				pread = pp[0]
				pwrite = pp[1]
				os.set_inheritable(pread, True)
				os.set_inheritable(pwrite, True)
				
				process_send = subprocess.Popen(send_command, stdout = pwrite, close_fds = False)
				process_receive = subprocess.Popen(receive_command, stdin = pread, close_fds = False)
				
				while process_send.returncode is None:
					sleep(1)
					process_send.poll()
				if process_send.returncode != 0:
					raise BackupError('btrfs send failed with return code {}'.format(process_send.returncode))
				else:
					while process_receive.returncode is None:
						sleep(1)
						process_receive.poll()
					if process_receive.returncode != 0:
						raise BackupError('btrfs receive failed with return code {}'.format(process_receive.returncode))
			finally:
				if pp is not None:
					os.close(pwrite)
					os.close(pread)
				if process_send is not None:
					if process_send.returncode is None:
						process_send.kill()
				if process_receive is not None:
					if process_receive.returncode is None:
						process_receive.kill()
				
			
			#delete old snapshots:
			ssd_source.purgeSnapshots()
			ssd_backup.scan()
			ssd_backup.purgeSnapshots()
		except Exception as e:
			logger.error('%s', e)
			logger.info('Backup job did not run successfully!')
			if source_snapshot is not None: #rollback on error
				sp = source_snapshot.getSnapshotPath()
				if sp.exists():
					logger.info('Rollback: Deleting subvolume "%s"', str(sp))
					btrfsutil.delete_subvolume(sp)
					if process_receive is not None:
						bsp = ssd_backup.getPath() / str(source_snapshot)
						if bsp.exists():
							logger.info('Rollback: Deleting subvolume "%s"', str(bsp))
							btrfsutil.delete_subvolume(bsp)
			raise e
		logger.info('Backup job finished successfully.')

class BackupError(Exception):
	"""Raised if something went wrong with the backup."""
	pass
