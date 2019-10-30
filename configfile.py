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


import configparser
import logging
import copy

import globalstuff
import cmdline
import verify
import util

from uuid import UUID
from pathlib import Path

#constants:
GLOBAL_LOGFILE = 'logfile'
GLOBAL_MOUNTDIR = 'mountdir'
GLOBAL_LOGLEVEL = 'loglevel'
GLOBAL_SNAPSHOTS = 'snapshots'
ENTRY_SNAPSHOTS = 'snapshots'
ENTRY_SOURCE = 'source'
ENTRY_SNAPSHOTDIR = 'snapshot-dir'
ENTRY_TARGET = 'backup-device'
ENTRY_TARGETDIR = 'backup-dir'
ENTRY_KEYFILE = 'keyfile'
MANDATORY_ENTRY_KEYS = ( ENTRY_SOURCE, ENTRY_SNAPSHOTDIR, ENTRY_TARGET )
#error strings
ERR_UNKNOWN_KEY = 'The key "{}" is not defined!'
ERR_INVALID_VALUE = 'Config Section [{}]: Value "{}" is not valid for key "{}"!'

logger = logging.getLogger(__name__)

option_mapping_defaults = { cmdline.ARG_LOGFILE: [ GLOBAL_LOGFILE, True ], \
												cmdline.ARG_LOGLEVEL: [ GLOBAL_LOGLEVEL, True ], \
												cmdline.ARG_MNT: [ GLOBAL_MOUNTDIR, True ], \
												cmdline.ARG_SNAPSHOTS: [ GLOBAL_SNAPSHOTS, True ] }

option_mapping_entry = { cmdline.ARG_NAME: None, \
											cmdline.ARG_SOURCE: [ ENTRY_SOURCE, False ], \
											cmdline.ARG_TARGET: [ ENTRY_TARGET, False ], \
											cmdline.ARG_TARGETDIR: [ ENTRY_TARGETDIR, True ], \
											cmdline.ARG_SNAPSHOTDIR: [ ENTRY_SNAPSHOTDIR, False ], \
											cmdline.ARG_SNAPSHOTS: [ ENTRY_SNAPSHOTS, True ], \
											cmdline.ARG_KEYFILE: [ ENTRY_KEYFILE, True ] }

class Configfile:
	def __init__(self, path: Path):
		verify.requireAbsolutePath(path)
		self._path = path
		self._cp = configparser.ConfigParser(delimiters = '=', comment_prefixes = '#', interpolation = None)
		self._cp.optionxform = str
		
	def read(self):
		if self._path.exists():
			self._cp.read(self._path)
	
	def write(self):
		if not self._path.exists():
			pdir = self._path.parent
			if not pdir.exists():
				pdir.mkdir(parents=True)
		try:
			with open(self._path, 'w') as cf:
				self._cp.write(cf)
		except PermissionError as e:
			raise ConfigfileError("""You don't have permission to write to the configuration file, your changes have not been saved!
Configuration file location: \"{}\"""".format(globalstuff.config_backups))
	
	def _addCmdlineData(self, section, mapping, data):
		for k, v in data.items():
			if not k in mapping:
				raise ConfigfileError(ERR_UNKNOWN_KEY.format(k))
			m = mapping[k]
			if m is None: #ignore command line args with nonexisting mapping
				continue
			if v is None and m[1]:
				if m[0] in section:
					del section[m[0]]
			elif v is None and not m[1]:
				raise globalstuff.Bug #mapping is configured incorrectly
			else:
				section[m[0]] = str(v)
	
	def _doConfigEntryFromCmdline(self, action, data):
		name = data[cmdline.ARG_NAME]
		if action == cmdline.ACTION_ADD:
			if self._cp.has_section(name):
				raise ConfigfileError('Entry "{}" already exists!'.format(name))
			self._cp.add_section(name)
		elif action == cmdline.ACTION_MODIFY:
			if not self._cp.has_section(name):
				raise ConfigfileError('Entry "{}" does not exist!'.format(name))
		else:
			raise globalstuff.Bug
		section = self._cp[name]
		self._addCmdlineData(section, option_mapping_entry, data)
	
	def addConfigEntryFromCmdline(self, data):
		"""Takes data parsed from the cmdline module's "_do_add" function
		and writes it in the config file."""
		self._doConfigEntryFromCmdline(cmdline.ACTION_ADD, data)
	
	def modifyConfigEntryFromCmdline(self, data):
		"""Takes data parsed from the cmdline module's "_do_modify" function
		and overwrites an already existing config file entry with the new data,
		then returns true. If no entry exists in the config file, no data will be written
		and the function will return false."""
		self._doConfigEntryFromCmdline(cmdline.ACTION_MODIFY, data)
	
	def addDefaultsFromCmdline(self, data):
		section = self._cp.defaults()
		self._addCmdlineData(section, option_mapping_defaults, data)
	
	def getConfigEntries(self):
		ret = dict()
		for s in self._cp.sections():
			ret[s] = self.getConfigEntry(s)
		return ret
	
	def getConfigEntry(self, name: str):
		if not self._cp.has_section(name):
			raise ConfigfileError('Entry "{}" does not exist in the configuration file!'.format(name))
		section = self._cp[name]
		return section
	
	def deleteConfigEntry(self, name: str):
		return self._cp.remove_section(name)
	
	def verifyConfigEntry(self, name: str):
		e = self.getConfigEntry(name)
		if not verify.backup_id(name):
			raise ConfigfileError('Backup entry "{}" has an invalid name!'.format(name))
		for k in MANDATORY_ENTRY_KEYS:
			if not k in e:
				raise ConfigfileError('Backup entry "{}": Mandatory key "{}" is missing!'.format(name, k))
		check_abspath = [ ENTRY_SOURCE, ENTRY_SNAPSHOTDIR ]
		if not verify.uuid(e[ENTRY_TARGET]):
			check_abspath.append(ENTRY_TARGET)
		if ENTRY_KEYFILE in e:
			check_abspath.append(ENTRY_KEYFILE)
		for k in check_abspath:
			try:
				verify.requireAbsolutePath(Path(e[k]))
			except verify.VerificationError:
				raise ConfigfileError('Backup entry "{}": Key "{}" requires an absolute file path!'.format(name, k))
		if ENTRY_SNAPSHOTS in e:
			try:
				verify.requireRightAmountOfSnapshots(int(e[ENTRY_SNAPSHOTS]))
			except verify.VerificationError:
				raise ConfigfileError('Backup entry "{}": Key "{}" has an invalid value!'.format(name, ENTRY_SNAPSHOTS))
		if ENTRY_TARGETDIR in e:
			try:
				verify.requireRelativePath(Path(e[ENTRY_TARGETDIR]))
			except verify.VerificationError:
				raise ConfigfileError('Backup entry "{}": Key "{}" requires a relative path!'.format(name, ENTRY_TARGETDIR))
	
	def loadGlobals(self):
		sectionName = 'GLOBALS'
		defaults = self._cp.defaults()
		for k, v in defaults.items():
			if k == GLOBAL_LOGFILE:
				if globalstuff.logfile_from_cmdline:
					continue
				p = Path(v)
				verify.requireAbsolutePath(p)
				globalstuff.logfile = Path(v)
			elif k == GLOBAL_LOGLEVEL:
				if globalstuff.debug_mode or globalstuff.loglevel_from_cmdline:
					continue
				ll = util.str_to_loglevel(v)
				if ll is None:
					raise ConfigfileError(ERR_INVALID_VALUE.format(sectionName, k, v))
			elif k == GLOBAL_MOUNTDIR:
				p = Path(v)
				verify.requireAbsolutePath(p)
				globalstuff.mountdir = Path(v)
			elif k == ENTRY_SNAPSHOTS:
				ss = int(v)
				if verify.snapshot_count(ss):
					globalstuff.default_snapshots = ss
				else:
					raise ConfigfileError(ERR_INVALID_VALUE.format(sectionName, k, v))
			else:
				raise ConfigfileError(ERR_UNKNOWN_KEY.format(k))

	
class ConfigfileError(Exception):
	def __init__(self, msg = None):
		if msg is not None:
			super().__init__(msg)
