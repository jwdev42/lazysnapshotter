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
import sys
from pathlib import Path
from . import backup, cmdline, configfile, globalstuff, logkit, mounts, sessionkit, verify

logger = logging.getLogger(__name__)

def _globalcmdline():
	"""Parse the global (pre-action) part of the command line options, then load its data into the program."""
	pcmd = cmdline.preAction()
	for k, v in pcmd.data.items():
		if k == cmdline.ARG_PRE_DEBUGMODE and v:
			globalstuff.debug_mode = True
			logkit.log.setLevel(logging.DEBUG, 3)
			logging.debug('Set debug mode.')
		elif k == cmdline.ARG_PRE_CONFIGFILE:
			globalstuff.config_backups = v
		elif k == cmdline.ARG_PRE_LOGFILE:
			logkit.log.addLogFile(Path(v))
		elif k == cmdline.ARG_PRE_LOGLEVEL:
			ll = util.str_to_loglevel(v)
			if ll is None:
				raise globalstuff.Bug
			logkit.log.setLevel(ll, 2)
	
def _loadConfig():
	"""Reads the configuration file and loads its global options."""
	cf = configfile.Configfile(globalstuff.config_backups)
	cf.read()
	cf.loadGlobals()
	return cf

def _fill_backup_entry(e, config, args):
	config_entry = config.getConfigEntry(e.name)
	config.verifyConfigEntry(e.name)
	e.flag_unmount = not args[cmdline.ARG_NOUMOUNT]
	if args[cmdline.ARG_KEYFILE] is not None:
		e.keyfile = args[cmdline.ARG_KEYFILE]
	elif configfile.ENTRY_KEYFILE in config_entry:
		e.keyfile = config_entry[configfile.ENTRY_KEYFILE]
	if configfile.ENTRY_SNAPSHOTS in config_entry:
		e.snapshots = int(config_entry[configfile.ENTRY_SNAPSHOTS])
	else:
		e.snapshots = globalstuff.default_snapshots
	if configfile.ENTRY_TARGETDIR in config_entry:
		e.backup_dir_relative = Path(config_entry[configfile.ENTRY_TARGETDIR])
	e.source = Path(config_entry[configfile.ENTRY_SOURCE])
	e.snapshot_dir = Path(config_entry[configfile.ENTRY_SNAPSHOTDIR])
	if verify.uuid(config_entry[configfile.ENTRY_TARGET]):
		e.backup_volume = config_entry[configfile.ENTRY_TARGET]
	else:
		e.backup_volume = Path(config_entry[configfile.ENTRY_TARGET])
	e.verify()

def _run_backup(config, args):
	entry = backup.Entry(name = args[cmdline.ARG_NAME])
	sessionkit.session.registerBackup(entry.name, globalstuff.config_backups)
	try:
		_fill_backup_entry(entry, config, args)
		logkit.log.fmtAppend('backup_name', 'jobname: {}'.format(entry.name))
		logkit.log.fmtAppend('backup_id', 'jobid: {}'.format(str(sessionkit.session.session_id)))
		
		dev = mounts.device_by_state(entry.backup_volume)
		try:
			logger.info('Arming backup drive')
			dev.arm(sessionkit.session.getMountDir(create_parent = True, mkdir = True),
			luks_name = str(sessionkit.session.session_id), keyfile = entry.keyfile)
			backup_dir = None
			if entry.backup_dir_relative is not None:
				backup_dir = dev.mountPoint().joinpath(entry.backup_dir_relative)
			else:
				backup_dir = dev.mountPoint()
			logger.info('Starting backup')
			backup.send_and_receive(entry.source, entry.snapshot_dir, backup_dir)
			logger.info('Removing old snapshots')
			backup.purge_old_snapshots(entry.snapshot_dir, entry.snapshots)
			backup.purge_old_snapshots(backup_dir, entry.snapshots)
			logger.info('Syncing backup drive')
			trans_id = btrfsutil.start_sync(dev.mountPoint())
			btrfsutil.wait_sync(dev.mountPoint(), trans_id)
		finally:
			if entry.flag_unmount:
				logger.info('Disarming backup drive')
				dev.disarm()
			else:
				logger.info('Backup drive stays online through user request')
	finally:
		sessionkit.session.releaseBackup()

class NoActionDefinedException(Exception):
	pass

def main():
	try:
		#initialize global variables
		sessionkit.session = sessionkit.Session(Path('/run/lazysnapshotter'))
		logkit.log = logkit.LogKit(logging.INFO)
		
		_globalcmdline()
		pcmd = cmdline.action()
		if pcmd is None:
			raise NoActionDefinedException
		cf = _loadConfig()
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
				sessionkit.session.setup()
				_run_backup(cf, pcmd.data)
			finally:
				sessionkit.session.cleanup()
	except NoActionDefinedException:
		pass
	except Exception as e:
		globalstuff.printException(e)
		if globalstuff.status == globalstuff.EXIT_SUCCESS:
			globalstuff.status == globalstuff.EXIT_FAILURE
	finally:
		logging.shutdown()
		sys.exit(globalstuff.status)
