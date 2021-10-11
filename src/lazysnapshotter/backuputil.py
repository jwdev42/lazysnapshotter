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

from . import backup, cmdline, configfile, globalstuff, verify
from pathlib import Path

def create_backup_entry(config, args):
	"""Return a new backup entry compiled from config file data and command line arguments."""
	e = backup.Entry(name = args[cmdline.ARG_NAME])
	config_entry = config.getConfigEntry(e.name)
	config.verifyConfigEntry(e.name)
	e.flag_unmount = not args[cmdline.ARG_NOUMOUNT]
	if args[cmdline.ARG_KEYFILE] is not None:
		e.keyfile = args[cmdline.ARG_KEYFILE]
	elif configfile.ENTRY_KEYFILE in config_entry:
		e.keyfile = Path(config_entry[configfile.ENTRY_KEYFILE])
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
	return e
