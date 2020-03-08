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

import logging
import traceback
import sys
import os.path

from . import cmdline
from . import configfile
from . import globalstuff
from . import libbackup
from . import verify
from . import mounts
from . import util

from uuid import UUID
from pathlib import Path
from subprocess import CalledProcessError

logger = logging.getLogger(__name__)

def globalcmdline():
	"""Parse the global (pre-action) part of the command line options, then load its data into the program."""
	pcmd = cmdline.preAction()
	for k, v in pcmd.data.items():
		if k == cmdline.ARG_PRE_DEBUGMODE and v:
			globalstuff.debug_mode = True
			globalstuff.log.setLevel(logging.DEBUG, 3)
			logging.debug('Set debug mode.')
		elif k == cmdline.ARG_PRE_CONFIGFILE:
			globalstuff.config_backups = v
		elif k == cmdline.ARG_PRE_LOGFILE:
			globalstuff.log.addLogFile(Path(v))
		elif k == cmdline.ARG_PRE_LOGLEVEL:
			ll = util.str_to_loglevel(v)
			if ll is None:
				raise globalstuff.Bug
			globalstuff.log.setLevel(ll, 2)
	
def loadConfig():
	"""Reads the configuration file and loads its global options."""
	cf = configfile.Configfile(globalstuff.config_backups)
	cf.read()
	cf.loadGlobals()
	return cf

def _b_error(e: Exception, name: str, reason: str = None, advice:str = None):
	"""Called by runBackup on specific errors, creates a human-readable error description."""
	print('ERROR:\t\tBackup "{}" could not be run!'.format(name), file = sys.stderr)
	if reason is not None:
		print('Reason:\t\t{}'.format(reason), file = sys.stderr)
	if advice is not None:
		print('Advice:\t\t{}'.format(advice), file = sys.stderr)
	print('Exception:', end = '\t', file = sys.stderr)
	raise e
	
def runBackup(cf, backup_params):
	try:
		name = backup_params[cmdline.ARG_NAME]
		unmount = not backup_params[cmdline.ARG_NOUMOUNT] #controls if the backup volume will be unmounted after the backup
		keyfile = backup_params[cmdline.ARG_KEYFILE]
		unmap = False #controls if the luks volume will be unmapped after the backup
		cfe = cf.getConfigEntry(name)
		cf.verifyConfigEntry(name)
		globalstuff.log.fmtAppend('backup_name', 'jobname: {}'.format(name))
		globalstuff.log.fmtAppend('backup_id', 'jobid: {}'.format(str(globalstuff.session.session_id)))
		be = libbackup.BackupEntry(name)
		backup = libbackup.Backup(be)
		
		globalstuff.session.registerBackup(name, globalstuff.config_backups)
		
		if configfile.ENTRY_SNAPSHOTS in cfe:
			be.setSnapshots(int(cfe[configfile.ENTRY_SNAPSHOTS]))
		else:
			be.setSnapshots(globalstuff.default_snapshots)
		if configfile.ENTRY_TARGETDIR in cfe:
				be.setBackupDir(Path(cfe[configfile.ENTRY_TARGETDIR]))
		be.setSourceSubvolume(Path(cfe[configfile.ENTRY_SOURCE]))
		be.setSourceSnapshotDir(Path(cfe[configfile.ENTRY_SNAPSHOTDIR]))
					
		#u_dev: unknown dev, could be a luks device or a partition, as uuid or absolute path
		u_dev = cfe[configfile.ENTRY_TARGET]
		
		if verify.uuid(u_dev):
				u_dev = mounts.getBlockDeviceFromUUID(UUID(u_dev))
		logger.debug('Using backup device "{}".'.format(u_dev))
		backup_device = Path(u_dev)
		try:
			#verifyConfigEntry() already validated an absolute path
			verify.requireExistingPath(backup_device)
		except verify.VerificationError:
			raise globalstuff.ApplicationError('Backup device does not exist: "{}".'.format(backup_device))
		
		isluks = None
		try:
			isluks = mounts.isLuks(backup_device)
		except CalledProcessError as e:
			_b_error(e, name, reason = 'Cryptsetup exited with an error when checking if the backup device was a luks container.', \
			advice = 'Please make sure you have sufficient rights to access the backup device.')
		try:
			mountpoint = None
			be.setTargetDevice(Path(backup_device))
			if isluks:
				logger.debug('Backup device is a LUKS container.')
				mapping = mounts.getLuksMapping(backup_device)
				if mapping is not None:
					logger.debug('LUKS container is already open.')
					backup.setLuksMapping(Path(mapping))
				else:
					logger.debug('Opening LUKS container.')
					unmap = True
					if configfile.ENTRY_KEYFILE in cfe or keyfile is not None:
						if keyfile is None:
							keyfile = Path(cfe[configfile.ENTRY_KEYFILE])
						try:
							verify.requireExistingPath(keyfile)
						except verify.VerificationError as e:
							raise globalstuff.ApplicationError('Keyfile does not exist: "{}"!'.format(keyfile))
						backup.openLuks(keyfile = keyfile)
					else:
						backup.openLuks()
				mountpoint = mounts.getMountpoint(backup.getLuksMapping())
			else:
				logger.debug('Backup device is a Partition.')
				mountpoint = mounts.getMountpoint(be.getTargetDevice())
			if mountpoint is None:
				logger.debug('Mounting Partition.')
				backup.mount(globalstuff.session.getMountDir(create_parent = True))
			else:
				logger.debug('Partition is already mounted.')
				backup.setMountPoint(mountpoint)
				unmount = False
			bd = be.getBackupDir()
			if bd is not None:
				be.setTargetSnapshotDir(backup.getMountPoint() / bd)
			else:
				be.setTargetSnapshotDir(backup.getMountPoint())
				
			backup.run()
		finally:
			if unmount:
				if backup.unmount(tries = 2, interval = 90):
					backup.removeMountPoint()
			if unmap:
				backup.closeLuks()
	finally:
		globalstuff.session.releaseBackup()
	
def run():
	try:
		globalcmdline()
		pcmd = cmdline.action()
		if pcmd is None:
			raise NoActionDefinedException
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
			if pcmd.data.verbose:
				cf.printConfigEntries(verbose = True)
			elif len(pcmd.data.entries) > 0:
				for e in pcmd.data.entries:
					cf.printConfigEntry(e)
			else:
				cf.printConfigEntries()
		elif pcmd.action == cmdline.ACTION_RUN:
			try:
				globalstuff.session.setup()
				runBackup(cf, pcmd.data)
			finally:
				globalstuff.session.cleanup()
	except NoActionDefinedException as e:
		pass
	except Exception as e:
		globalstuff.printException(e)
		if globalstuff.status == globalstuff.EXIT_SUCCESS:
			globalstuff.status == globalstuff.EXIT_FAILURE
	finally:
		logging.shutdown()
		sys.exit(globalstuff.status)

class NoActionDefinedException(Exception):
	pass
