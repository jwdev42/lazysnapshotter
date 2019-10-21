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
import subprocess
import shutil
import uuid
import os
import os.path
import copy
import warnings
from pathlib import Path
from time import sleep

import globalstuff
import verify
import mounts
import btrfsutil

logger = logging.getLogger(__name__)

class BackupEntry:
	def __init__(self, name: str):
		self._name = name
		self._sourceSubvolume = None #the subvolume to backup
		self._sourceSnapshotDir = None
		self._cryptDevice = None
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
			self._sourceSnapshotDir = btrfsutil.SnapshotDir(ss_dir, keep = self._snapshots)
		else:
			self._sourceSnapshotDir = btrfsutil.SnapshotDir(ss_dir)
	
	def setCryptDevice(self, path: Path):
		"""Sets the passed block device as the encrypted target container on the backup medium."""
		verify.requireAbsolutePath(path)
		verify.requireExistingPath(path)
		self._cryptDevice = path
		
	def setCryptUUID(self, crypt_uuid):
		"""like setCryptDevice, but takes the device's UUID."""
		dev = mounts.getBlockDeviceFromUUID(crypt_uuid)
		self.setCryptDevice(dev)
	
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
		self._targetSnapshotDir = btrfsutil.SnapshotDir(tss_dir, self._snapshots)
	else:
		self._targetSnapshotDir = btrfsutil.SnapshotDir(tss_dir)
	
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
	
	def getCryptDevice(self):
		return copy.deepcopy(self._cryptDevice)
	
	def getTargetDevice(self):
		return copy.deepcopy(self._targetDevice)
		
	def getBackupDir(self):
		return copy.deepcopy(self._backupDir)
		
	def getTargetSnapshotDir(self):
		return self._targetSnapshotDir
	
	def getSnapshots(self):
		return copy.deepcopy(self._snapshots)

class Backup:
	def __init__(self, entry: 'libbackup.BackupEntry'):
		if not isinstance(entry, BackupEntry):
			raise TypeError('arg 1 must be of libbackup.BackupEntry')
		self._entry = entry
		self._mountPoint = None
		self._mountPointCreated = False
		
	def _setMountPoint(self, path):
		verify.requireAbsolutePath(path)
		if not path.is_mount():
			raise globalstuff.ApplicationError('Path "{}" is expected to be a mount point!'.format(path))
		self._mountPoint = path
	
	def getEntry(self):
		return self._entry
	
	def isLuks(self):
		if isinstance(self.getEntry().getCryptDevice(), Path):
			return True
		return False
	
	def isMounted(self):
		dev = self.getEntry().getTargetDevice()
		if mounts.deviceMountPoints(str(dev)) > 0:
			return True
		return False
			
	def openLuks(self, keyfile=None):
		"""Opens the LUKS container specified in the BackupEntry, sets the BackupEntry's
		Target Device as a side effect."""
		dev = self._entry.getCryptDevice()
		verify.requireAbsolutePath(dev)
		if keyfile is not None and not isinstance(keyfile, Path):
			raise TypeError('arg 1 must be of pathlib.Path')
		name = str(uuid.uuid4())
		command = [ shutil.which('cryptsetup'), 'open', str(dev), name ]
		if keyfile is not None:
			command.append('--key-file')
			command.append(str(keyfile))
		res = subprocess.run(command)
		res.check_returncode()
		p = Path('/dev/mapper/') / Path(name)
		verify.requireExistingPath(p)
		logger.debug('LUKS Container "%s" is open at "%s".', str(dev), str(p))
		e = self.getEntry()
		#side effect: set the target device for mounting
		e.setTargetDevice(p)
	
	def closeLuks(self):
		dev = self.getEntry().getTargetDevice()
		if self.isMounted():
			logger.warning('Cannot close LUKS device "%s" as it is still mounted!', str(dev))
			return False
		verify.requireExistingPath(dev)
		command = [ shutil.which('cryptsetup'), 'close', str(dev) ]
		res = subprocess.run(command)
		try:
			res.check_returncode()
		except subprocess.CalledProcessError as e:
			globalstuff.printException(e)
			logger.error('Failed to close LUKS container "%s"!', str(self._mountPoint))
			return False
		logger.debug('LUKS Container at "%s" was closed.', str(dev))
		return True
	
	def mount(self, path: Path = None):
		mountpath = None
		if path is None:
			appendix = Path(self.getEntry().getName())
			verify.requireAbsolutePath(globalstuff.mountdir)
			verify.requireExistingPath(globalstuff.mountdir)
			mountpath = globalstuff.mountdir / appendix
		else:
			mountpath = path
		if not mountpath.exists():
			os.mkdir(mountpath)
			self._mountPointCreated = True
		dev = self._entry.getTargetDevice()
		verify.requireExistingPath(dev)
		command = [ shutil.which('mount'), str(dev), str(mountpath) ]
		res = subprocess.run(command)
		res.check_returncode()
		self._mountPoint = mountpath
		logger.debug('Device "%s" mounted at "%s".', str(dev), str(self._mountPoint))
		#set the targetSnapshotDir for the contained BackupEntry as a side effect
		e = self.getEntry()
		bd = e.getBackupDir()
		if bd is None:
			e.setTargetSnapshotDir(self._mountPoint)
		else:
			e.setTargetSnapshotDir(self._mountPoint / bd)
		
		
	def wasMountPointCreated(self):
		"""Returns True if the mount()-Method created the directory of the mount point, false otherwise."""
		return copy.deepcopy(self._mountPointCreated)
	
	def unmount(self):
		verify.requireExistingPath(self._mountPoint)
		if not self.isMounted():
			logger.warning('Cannot unmount "%s" as it is not mounted!', str(self._mountPoint))
			return False
		command = [ shutil.which('umount'), str(self._mountPoint) ]
		res = subprocess.run(command)
		try:
			res.check_returncode()
		except subprocess.CalledProcessError as e:
			globalstuff.printException(e)
			logger.error('Failed to unmount "%s"!', str(self._mountPoint))
			return False
		logger.debug('"%s" was unmounted.', str(self._mountPoint))
		#remove directory if it was created by mount():
		if self.wasMountPointCreated():
			os.rmdir(self._mountPoint)
		return True
	
	def run(self):
		e = self.getEntry()
		logger.info('Starting Backup "%s".', e.getName())
		ssd_source = e.getSourceSnapshotDir()
		ssd_source.scan()
		#lsssbb = latest source snapshot before backup
		lsssbb = ssd_source.getNewestSnapshot()
		#lsss = latest source snapshot
		lsss = ssd_source.createSnapshot(e.getSourceSubvolume())
		ssd_backup = e.getTargetSnapshotDir()
		ssd_backup.scan()
		#ltssbb = latest target snapshot before backup
		ltssbb = ssd_backup.getNewestSnapshot()
		
		send_command = [ shutil.which('btrfs'), 'send' ]
		
		if str(lsssbb) == str(ltssbb) and lsssbb is not None:
			#incremental backup
			send_command.append('-p')
			send_command.append(str(lsssbb.getSnapshotPath()))
			send_command.append(str(lsss.getSnapshotPath()))
			logger.info('Parent Snapshot: "%s".', str(lsssbb.getSnapshotPath()))
		else:
			#full backup
			send_command.append(str(lsss.getSnapshotPath()))
		logger.info('Snapshot: "%s".', str(lsss.getSnapshotPath()))
		logger.info('Target Directory: "%s".', str(ssd_backup.getPath()))
		
		receive_command = [ shutil.which('btrfs'), 'receive', '-e', str(ssd_backup.getPath()) ]
		
		pp = None
		try:
			pp = os.pipe()
			pread = pp[0]
			pwrite = pp[1]
			os.set_inheritable(pread, True)
			os.set_inheritable(pwrite, True)
			
			process_send = subprocess.Popen(send_command, stdout = pwrite, close_fds = False)
			process_receive = subprocess.Popen(receive_command, stdin = pread, close_fds = False)
			
			return_send = process_send.poll()
			while return_send is None:
				sleep(1)
				return_send = process_send.poll()
			logger.debug('"btrfs send" returned "%s"', str(return_send))
			
			return_receive = process_receive.poll()
			while return_receive is None:
				sleep(1)
				return_receive = process_send.poll()
			logger.debug('"btrfs receive" returned "%s"', str(return_receive))
		
			if return_send is 0 and return_receive is 0:
				logger.info('Backup "%s" finished successfully.', e.getName())
			if return_send is not 0:
				#error in btrfs send
				raise BackupError('btrfs send returned ' + str(return_send))
			if return_receive is not 0:
				#error in btrfs receive
				raise BackupError('btrfs receive returned ' + str(return_receive))
		finally:
			if pp is not None:
				os.close(pwrite)
				os.close(pread)
		
		#delete old snapshots:
		ssd_source.purgeSnapshots()
		ssd_backup.scan()
		ssd_backup.purgeSnapshots()

class BackupError(Exception):
	"""Raised if something went wrong with the backup."""
	pass
