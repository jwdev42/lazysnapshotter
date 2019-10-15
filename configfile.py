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

from uuid import UUID
from pathlib import Path

#constants:
GLOBAL_LOGFILE = 'log'
GLOBAL_MOUNTDIR = 'mount'
GLOBAL_LOGLEVEL = 'loglevel'
GLOBAL_SNAPSHOTS = 'snapshots'
ENTRY_SNAPSHOTS = 'snapshots'
ENTRY_SOURCE = 'source'
ENTRY_SNAPSHOTDIR = 'snapshot_dir'
ENTRY_TARGET = 'target'
ENTRY_TARGETDIR = 'target_dir'

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
											cmdline.ARG_SNAPSHOTS: [ ENTRY_SNAPSHOTS, True ] }

class Configfile:
	def __init__(self, path: Path):
		verify.requireAbsolutePath(path)
		self._path = path
		self._cp = configparser.ConfigParser(delimiters = '=', comment_prefixes = '#')
		
	def read(self):
		if self._path.exists():
			self._cp.read(self._path)
	
	def write(self):
		if not self._path.exists():
			pdir = self._path.parent
			if not pdir.exists():
				pdir.mkdir(parents=True)
		with open(self._path, 'w') as cf:
			self._cp.write(cf)
		
	def isConfigEntryComplete(self, name: str):
		if not self._cp.has_section(name):
			return False
		has = { ENTRY_SOURCE: False, \
					ENTRY_SNAPSHOTDIR: False, \
					ENTRY_TARGET: False, \
					ENTRY_TARGETDIR: False }
		section = self._cp[name]
		
		for k, v in section.items():
			if k in has:
				has[k] = True
		
		for k, v in has.items():
			if not has[k]:
				return False
		return True
	
	def _addCmdlineData(self, section, mapping, data):
		for k, v in data.items():
			if not k in mapping:
				raise UnknownKeyError(k)
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
		if cmdline.ARG_NAME not in data:
			raise NameNotDefinedError
		name = data[cmdline.ARG_NAME]
		if action == cmdline.ACTION_ADD:
			if self._cp.has_section(name):
				raise ConfigfileException('Entry "{}" already exists!'.format(name))
			self._cp.add_section(name)
		elif action == cmdline.ACTION_MODIFY:
			if not self._cp.has_section(name):
				raise ConfigfileException('Entry "{}" does not exist!'.format(name))
		else:
			raise globalstuff.Bug
		section = self._cp[name]
		self._addCmdlineData(section, option_mapping_entry, data)
		if not self.isConfigEntryComplete(name):
			raise EntryIncompleteException(name)
	
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
			return None
		section = self._cp[name]
		return section
	
	def deleteConfigEntry(self, name: str):
		return self._cp.remove_section(name)
		
	def loadGlobals(self):
		sectionName = 'GLOBALS'
		defaults = self._cp.defaults()
		for k, v in defaults.items():
			if k == GLOBAL_LOGFILE:
				p = Path(v)
				verify.requireAbsolutePath(p)
				globalstuff.logfile = Path(v)
			elif k == GLOBAL_LOGLEVEL:
				if not v in verify.LOGLEVELS:
					raise InvalidValueError(sectionName, k, v)
				if v == 'CRITICAL':
					globalstuff.loglevel = logging.CRITICAL
				elif v == 'ERROR':
					globalstuff.loglevel = logging.ERROR
				elif v == 'WARNING':
					globalstuff.loglevel = logging.WARNING
				elif v == 'INFO':
					globalstuff.loglevel = logging.INFO
				elif v == 'DEBUG':
					globalstuff.loglevel = logging.DEBUG
			elif k == GLOBAL_MOUNTDIR:
				p = Path(v)
				verify.requireAbsolutePath(p)
				globalstuff.mountdir = Path(v)
			elif k == ENTRY_SNAPSHOTS:
				ss = int(v)
				if verify.snapshot_count(ss):
					globalstuff.default_snapshots = ss
				else:
					raise InvalidValueError(sectionName, k, v)
			else:
				raise UnknownKeyError(k)

	
class ConfigfileException(Exception):
	pass				

class NameNotDefinedError(ConfigfileException):
	pass

class UnknownKeyError(ConfigfileException):
	def __init__(self, key):
		self.message = 'The key "' + key + '" is not defined!'

class InvalidValueError(ConfigfileException):
	def __init__(self, section: str, key: str, value: str):
		self.message = 'Config Section [{}]: Value "{}" is not valid for key "{}"!'.format(section, value, key)

class MissingKeyError(ConfigfileException):
	def __init__(self, name, key):
		self.message = 'The key "' + key + '" is missing in backup entry "' + name + '"!'

class EntryIncompleteException(ConfigfileException):
	def __init__(self, name):
		self.message = 'The backup entry "' + name + '" is incomplete!'
