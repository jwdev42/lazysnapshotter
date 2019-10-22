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
import traceback
import sys
import os.path

import cmdline
import configfile
import globalstuff
import libbackup
import verify
import mounts
import util

from uuid import UUID
from pathlib import Path

logger = logging.getLogger(__name__)

def globalcmdline():
	"""Parse the global (pre-action) part of the command line options, then load its data into the program."""
	pcmd = cmdline.preAction()
	for k, v in pcmd.data.items():
		if k == cmdline.ARG_PRE_DEBUGMODE and v:
			globalstuff.debug_mode = True
			globalstuff.loglevel = logging.DEBUG
		elif k == cmdline.ARG_PRE_CONFIGFILE:
			globalstuff.config_backups = v
		elif k == cmdline.ARG_PRE_LOGFILE:
			globalstuff.logfile = v
			globalstuff.logfile_from_cmdline = True
		elif k == cmdline.ARG_PRE_LOGLEVEL:
			ll = util.str_to_loglevel(v)
			if ll is None:
				raise globalstuff.Bug
			if not globalstuff.debug_mode:
				globalstuff.loglevel = ll
				globalstuff.loglevel_from_cmdline = True


def setupLogger():
	f = '%(asctime)s: %(levelname)s - %(message)s'
	logging.basicConfig(filename = globalstuff.logfile, level = globalstuff.loglevel, format = f, style = '%')
	
def loadConfig():
	"""Reads the configuration file and loads its global options."""
	cf = configfile.Configfile(globalstuff.config_backups)
	cf.read()
	cf.loadGlobals()
	return cf

def createMountDir():
	if not os.path.exists(globalstuff.mountdir):
		os.mkdir(globalstuff.mountdir)
		logger.debug('Created mount directory "{}".'.format(str(globalstuff.mountdir)))
	elif not os.path.isdir(globalstuff.mountdir):
		raise globalstuff.ApplicationError('"{}" is expected to be a directory!'.format(globalstuff.mountdir))
	else:
		logger.debug('Mount directory "{}" already exists.'.format(str(globalstuff.mountdir)))

def cleanMountDir():
	if os.path.isdir(globalstuff.mountdir):
		if len(os.listdir(globalstuff.mountdir)) == 0:
			os.rmdir(globalstuff.mountdir)
			logger.debug('Removed mount directory "{}".'.format(str(globalstuff.mountdir)))

def _b_error(e: Exception, name: str, reason: str = None, advice:str = None):
	"""Called by runBackup on specific errors, creates a human-readable error description."""
	print('ERROR: Backup "{}" could not be run!'.format(name), file = sys.stderr)
	if reason is not None:
		print('Reason: {}\n'.format(reason), file = sys.stderr)
	if advice is not None:
		print('Advice: {}\n'.format(advice), file = sys.stderr)
	raise e
	
def runBackup(cf, backup_params):
	
	name = backup_params[0]
	unmount = not backup_params[1] #controls if the backup volume will be unmounted after the backup
	unmap = False #controls if the luks volume will be unmapped after the backup
	cfe = cf.getConfigEntry(name)
	if cfe is None:
		print('Backup "{}" does not exist!'.format(name))
		return
	be = libbackup.BackupEntry(name)
	backup = libbackup.Backup(be)
	
	if configfile.ENTRY_SNAPSHOTS in cfe:
		try:
			be.setSnapshots(int(cfe[configfile.ENTRY_SNAPSHOTS]))
		except verify.VerificationError as e:
			_b_error(e, name, reason = 'The backup\'s custom snapshot amount is invalid.', \
			advice = 'Please set the backup entry\'s snapshot value between 1 and {}.'.format(globalstuff.max_snapshots))
	else:
		be.setSnapshots(globalstuff.default_snapshots)
	
	try:
		be.setSourceSubvolume(Path(cfe[configfile.ENTRY_SOURCE]))
	except verify.VerificationError as e:
		_b_error(e, name, reason = 'The backup source could not be validated.', \
		advice = 'Please make sure that the backup source exists and is a valid btrfs subvolume.')
	try:
		be.setSourceSnapshotDir(Path(cfe[configfile.ENTRY_SNAPSHOTDIR]))
	except verify.VerificationError as e:
		_b_error(e, name, reason = 'The snapshot directory could not be validated.', \
		advice = 'Please make sure that the snapshot directory exists.')
	if configfile.ENTRY_TARGETDIR in cfe:
		try:
			be.setBackupDir(Path(cfe[configfile.ENTRY_TARGETDIR]))
		except verify.VerificationError as e:
			_b_error(e, name, reason = 'The backup directory on the backup volume could not be validated.', \
			advice = 'Please make sure that the backup directory is provided as a relative path starting from the root directory of the backup volume.')
	
	#u_dev: unknown dev, could be a luks device or a partition, as uuid or absolute path
	u_dev = cfe[configfile.ENTRY_TARGET]
	
	if verify.uuid(u_dev):
		try:
			u_dev = mounts.getBlockDeviceFromUUID(UUID(u_dev))
		except verify.VerificationError as e:
			_b_error(e, name, reason = 'No block device found for the backup device\'s UUID.', \
			advice = 'Please make sure that the provided UUID is valid and the device is plugged in.')
	
	logger.debug('Using backup device "{}".'.format(u_dev))
	backup_device = Path(u_dev)
	try:
		verify.requireAbsolutePath(backup_device)
		verify.requireExistingPath(backup_device)
	except verify.VerificationError as e:
		_b_error(e, name, reason = 'Verification of the backup device failed.', \
		advice = """Please make sure that the backup device exists.
Be advised that the backup device must be provided as an absolute file path or a valid UUID.""")
	
	isluks = None
	try:
		isluks = mounts.isLuks(backup_device)
	except CalledProcessError as e:
		_b_error(e, name, reason = 'Cryptsetup exited with an error when checking if the backup device was a luks container.', \
		advice = 'Please make sure you have sufficient rights to access the backup device.')
	
	if isluks:
		logger.debug('Backup device is a LUKS container.')
		be.setCryptDevice(backup_device)
		dev = mounts.getLuksMapping(be.getCryptDevice())
		if dev is not None:
			logger.debug('LUKS container is already open.')
			be.setTargetDevice(Path(dev))
		else:
			logger.debug('Opening LUKS container.')
			backup.openLuks()
			unmap = True
	else:
		logger.debug('Backup device is a Partition.')
		be.setTargetDevice(backup_device)
	
	mp = mounts.getMountpoint(be.getTargetDevice())
	if mp is None:
		logger.debug('Mounting Partition.')
		backup.mount()
	else:
		logger.debug('Partition is already mounted.')
		bd = be.getBackupDir()
		if bd is not None:
			be.setTargetSnapshotDir(Path(mp) / bd)
		else:
			be.setTargetSnapshotDir(Path(mp))
		unmount = False
		
	backup.run()
	
	if unmount:
		backup.unmount()
	if unmap:
		backup.closeLuks()
	
def main():
	try:
		globalcmdline()
		pcmd = cmdline.action()
		if pcmd is None:
			sys.exit(globalstuff.status)
		cf = loadConfig()
		if pcmd.action == cmdline.ACTION_ADD:
			cf.addConfigEntryFromCmdline(pcmd.data)
			cf.write()
		elif pcmd.action == cmdline.ACTION_MODIFY:
			cf.modifyConfigEntryFromCmdline(pcmd.data)
			cf.write()
		elif pcmd.action == cmdline.ACTION_REMOVE:
			for e in pcmd.data:
				cf.deleteConfigEntry(e)
			cf.write()
		elif pcmd.action == cmdline.ACTION_GLOBAL:
			cf.addDefaultsFromCmdline(pcmd.data)
			cf.write()
		elif pcmd.action == cmdline.ACTION_LIST:
			for e in cf.getConfigEntries().keys():
				print(e)
		elif pcmd.action == cmdline.ACTION_RUN:
			try:
				createMountDir()
				for e in pcmd.data:
					runBackup(cf, e)
			finally:
				cleanMountDir()
	except Exception as e:
		globalstuff.printException(e)
		if globalstuff.status == globalstuff.EXIT_SUCCESS:
			globalstuff.status == globalstuff.EXIT_FAILURE
	finally:
		sys.exit(globalstuff.status)

main()
