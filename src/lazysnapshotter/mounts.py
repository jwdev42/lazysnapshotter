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


import os
import subprocess
import shutil
import json

from . import globalstuff, mount, verify
from enum import Enum
from uuid import UUID
from pathlib import Path

def getBlockDeviceFromUUID(block_uuid: UUID) -> Path:
	"""Return the path to a device by its UUID. Return None if no device was found"""
	base = Path('/dev/disk/by-uuid/')
	symlink = base.joinpath(str(block_uuid))
	if not symlink.exists():
		return None
	return base.joinpath(Path(os.readlink(symlink))).resolve()

def isLuks(path):
	command = [ shutil.which('cryptsetup'), 'isLuks', str(path) ]
	res = subprocess.run(command)
	if res.returncode == 0:
		return True
	elif res.returncode == 1:
		return False
	else:
		res.check_returncode()
	
def getLuksMapping(luks_dev) -> Path:
	command = [ shutil.which('lsblk'), '-J', '-p', str(luks_dev) ]
	res = subprocess.run(command, stdout=subprocess.PIPE)
	res.check_returncode()
	data = json.loads(bytes.decode(res.stdout))
	for e in data['blockdevices']:
		if e['name'] == str(luks_dev):
			if 'children' in e:
				for c in e['children']:
					if c['type'] == 'crypt':
						return Path(c['name'])
	return None

def getMountpoint(dev) -> Path:
	"""Returns the mount point for a given block device or None if no such device or mount point exists"""
	command = [ shutil.which('lsblk'), '-J', '-p', str(dev) ]
	res = subprocess.run(command, stdout=subprocess.PIPE)
	res.check_returncode()
	data = json.loads(bytes.decode(res.stdout))
	for e in data['blockdevices']:
		if e['name'] == str(dev):
			if 'mountpoints' in e:
				if len(e['mountpoints']) > 0:
					if e['mountpoints'][0] is not None:
						return Path(e['mountpoints'][0])
	return None

class DeviceState(Enum):
	UNKNOWN = 0
	INITIALIZED = 1 #constructor ran successfully
	DECRYPTED = 2 #device is a luks device and has been decrypted
	MOUNTED = 3

class StateMismatch(Exception):
	def __init__(self, expected_state, state):
		super().__init__('Expected state {}, got state {}'.format(expected_state, state))

class DeviceNotFound(Exception):
	pass

class Device:
	dev = None #UUID or Path
	is_luks: bool = False
	_dev_point: Path = None #block device of partition
	_crypt_point: Path = None #device-mapper block device
	_mount_point: Path = None #mount point
	_state: DeviceState = DeviceState.UNKNOWN
	
	def __init__(self, dev):
		self.dev = dev
		if verify.uuid(self.dev):
			self._dev_point = getBlockDeviceFromUUID(UUID(self.dev))
			if self._dev_point is None:
				raise DeviceNotFound(f'No block device found for UUID "{self.dev}"')
		else:
			self._dev_point = Path(self.dev)
		verify.requireAbsolutePath(self._dev_point)
		try:
			verify.requireExistingPath(self._dev_point)
		except verify.VerificationError:
			raise DeviceNotFound(f'Block device "{str(self._dev_point)}" does not exist')
		self.is_luks = isLuks(self._dev_point)
		self._state = DeviceState.INITIALIZED
	
	def __repr__(self):
		return f'Device("{self._dev_point}","{self._crypt_point}","{self._mount_point}",{self._state})'
	
	def _must_state(self, state):
		if self._state != state:
			raise StateMismatch(state, self._state)
	
	def mountPoint(self):
		self._must_state(DeviceState.MOUNTED)
		return self._mount_point
	
	def luksOpen(self, name: str, keyfile = None):
		self._must_state(DeviceState.INITIALIZED)
		command = [ shutil.which('cryptsetup'), 'open', str(self._dev_point), name ]
		if keyfile is not None:
			command.append('--key-file')
			command.append(str(keyfile))
		res = subprocess.run(command)
		res.check_returncode()
		self._crypt_point = Path('/dev/mapper/').joinpath(name)
		self._state = DeviceState.DECRYPTED
	
	def luksClose(self):
		self._must_state(DeviceState.DECRYPTED)
		command = [ shutil.which('cryptsetup'), 'close', str(self._crypt_point) ]
		res = subprocess.run(command)
		res.check_returncode()
		self._crypt_point = None
		self._state = DeviceState.INITIALIZED
		
	def mount(self, mount_point: Path):
		verify.requireExistingPath(mount_point)
		if not mount_point.is_absolute():
			mount_point = mount_point.resolve()
		block_dev = None
		if self.is_luks:
			self._must_state(DeviceState.DECRYPTED)
			block_dev = self._crypt_point
		else:
			self._must_state(DeviceState.INITIALIZED)
			block_dev = self._dev_point
		mount.mount(block_dev, mount_point)
		self._mount_point = mount_point
		self._state = DeviceState.MOUNTED
	
	def unmount(self):
		self._must_state(DeviceState.MOUNTED)
		mount.umount(self._mount_point)
		self._mount_point = None
		if self.is_luks:
			self._state = DeviceState.DECRYPTED
		else:
			self._state = DeviceState.INITIALIZED
	
	def arm(self, mount_point: Path, luks_name: str = None, keyfile: Path = None):
		"""Evaluate the status of the device, execute the required steps to mount the device, mount the device."""
		if self._state == DeviceState.UNKNOWN:
			raise StateMismatch(DeviceState.INITIALIZED, DeviceState.UNKNOWN)
		elif self._state == DeviceState.INITIALIZED:
			if self.is_luks:
				self.luksOpen(luks_name, keyfile)
			self.mount(mount_point)
		elif self._state == DeviceState.DECRYPTED:
			self.mount(mount_point)
		elif self._state == DeviceState.MOUNTED:
			return
		else:
			raise globalstuff.Bug('You\'re not supposed to be here')
	
	def disarm(self):
		"""Evaluate the status of the device, execute the required steps to close the device, close the device."""
		if self._state == DeviceState.UNKNOWN:
			raise StateMismatch(DeviceState.INITIALIZED, DeviceState.UNKNOWN)
		elif self._state == DeviceState.INITIALIZED:
			return
		elif self._state == DeviceState.DECRYPTED:
			self.luksClose()
		elif self._state == DeviceState.MOUNTED:
			self.unmount()
			if self.is_luks:
				self.luksClose()
		else:
			raise globalstuff.Bug('You\'re not supposed to be here')

def device_by_state(dev) -> Device:
	"""evaluate the state of device dev (UUID or Path) and return an instance of Device that represents that state"""
	new_dev = Device(dev)
	def chk_mnt(dev):
		mnt = getMountpoint(dev)
		if mnt is not None:
			new_dev._mount_point = mnt
			new_dev._state = DeviceState.MOUNTED
	if new_dev.is_luks:
		mapping = getLuksMapping(new_dev._dev_point)
		if mapping is not None:
			new_dev._crypt_point = mapping
			new_dev._state = DeviceState.DECRYPTED
			chk_mnt(new_dev._crypt_point)
	else:
		chk_mnt(new_dev._dev_point)
	return new_dev
