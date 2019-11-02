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


import sys

from collections import deque
from pathlib import Path
from uuid import UUID

import globalstuff
import verify

#constants:
ACTION_ADD = 'add'
ACTION_MODIFY = 'modify'
ACTION_REMOVE = 'remove'
ACTION_LIST = 'list'
ACTION_RUN = 'run'
ACTION_GLOBAL = 'global'
ARG_PRE_CONFIGFILE = '--configfile'
ARG_PRE_DEBUGMODE = '--debug'
ARG_PRE_LOGFILE = '--logfile'
ARG_PRE_LOGLEVEL = '--loglevel'
ARG_NAME = '--name'
ARG_SOURCE = '--source'
ARG_TARGET = '--backup-device'
ARG_TARGETDIR = '--backup-dir'
ARG_SNAPSHOTDIR = '--snapshot-dir'
ARG_SNAPSHOTS = '--snapshots'
ARG_NOUMOUNT = '--nounmount'
ARG_LOGFILE = '--logfile'
ARG_LOGLEVEL = '--loglevel'
ARG_MNT = '--mountdir'
ARG_KEYFILE = '--keyfile'
ARG_VERBOSE = '--verbose'
KEY_BACKUPID = 'backupid'
REQUIRED_ENTRY_OPTIONS = ( ARG_NAME, ARG_SOURCE, ARG_TARGET, ARG_SNAPSHOTDIR )
ERR_BACKUP_ID = '"{}" is not a valid backup identifier!'
ERR_INVALID_COMMAND = '"{}" is not a valid command!'
ERR_INVALID_ARGUMENT = '"{}" is not a valid argument!'
ERR_DUPLICATE_ARGUMENT = '"{}" can only be specified once!'
ERR_MISSING_ARGUMENT = 'Action "{}" needs an Argument!'

args = deque(sys.argv)
args.popleft() #remove program name from args

class ProcessedCMDline():
	"""Container class that stores the processed command line."""
	def __init__(self):
		self.action = None
		self.data = None	

class ListData():
	def __init__(self):
		self.verbose = False
		self.entries = list()

def displayValidCommands():
	print('Valid commands:')
	print('\t{}'.format(ACTION_GLOBAL))
	print('\t{}'.format(ACTION_ADD))
	print('\t{}'.format(ACTION_MODIFY))
	print('\t{}'.format(ACTION_REMOVE))
	print('\t{}'.format(ACTION_LIST))
	print('\t{}'.format(ACTION_RUN))

def displayEntryExample():
	print('Minimal backup entry example:')
	print('\t{} example {} /my/subvolume/I/want/to/save {} /my/snapshots {} /dev/sdf2'\
	.format(ARG_NAME, ARG_SOURCE, ARG_SNAPSHOTDIR, ARG_TARGET))

def isEntryComplete(data):
	for e in REQUIRED_ENTRY_OPTIONS:
		if not e in data:
			return False
	return True

def preAction():
	res = ProcessedCMDline()
	_do_pre(res)
	return res

def action():
	"""Parse rest of the command line after the global options have been processed."""
	return _action()

def _action():
	"""Implementation to be called by action()."""
	res = ProcessedCMDline()
	if not len(args) > 0:
		displayValidCommands()
		return None
	if len(args) > 0:
		res.action = args[0]
		args.popleft()
		if res.action == ACTION_ADD:
			res = _do_add(res)
			if not isEntryComplete(res.data):
				displayEntryExample()
				raise CommandLineError('You entered an incomplete backup entry!')
			return res
		elif res.action == ACTION_MODIFY:
			return _do_modify(res)
		elif res.action == ACTION_REMOVE:
			return _do_remove(res)
		elif res.action == ACTION_LIST:
			return _do_list(res)
		elif res.action == ACTION_RUN:
			return _do_run(res)
		elif res.action == ACTION_GLOBAL:
			return _do_global(res)
		else:
			displayValidCommands()
			raise CommandLineError(ERR_INVALID_COMMAND.format(res.action))
	else:
		displayValidCommands()
		raise CommandLineError('No command given!')
	return None

def _arg_helper(data, arg, params):
	if arg in data:
		raise CommandLineError(ERR_DUPLICATE_ARGUMENT.format(arg))
	if len(args) < params:
		msg = None
		if params == 1:
			msg = 'Argument "{}" needs an option!'.format(arg)
		else:
			msg = 'Argument "{}" needs {} options!'.format(arg, params)
		raise CommandLineError(msg)

def _arg_optionless(data, arg):
	if len(args) == 0:
		_arg_helper(data, arg, 0)
		data[arg] = None
		return True
	elif args[0].startswith('--'):
		_arg_helper(data, arg, 0)
		data[arg] = None
		return True
	return False

def _parse_arg_with_absolute_path(arg, data):
	_arg_helper(data, arg, 1)
	p = Path(args[0])
	verify.requireAbsolutePath(p)
	data[arg] = p
	args.popleft()

def _parse_snapshots(arg, data):
	_arg_helper(data, arg, 1)
	ss = int(args[0])
	if verify.snapshot_count(ss):
		data[arg] = ss
		args.popleft()
	else:
		raise CommandLineError('Only between 1 and {} snapshots are supported!'.format(globalstuff.max_snapshots))

def _pre_path_helper(arg, data, path):
	_arg_helper(data, arg, 1)
	if not path.is_absolute():
		path = path.resolve()
	data[arg] = path
	args.popleft()

def _do_pre(res):
	"""Process global command line arguments before an action is applied"""
	res.data = dict()
	while len(args) > 0:
		arg = args[0]
		args.popleft()
		if arg == ARG_PRE_CONFIGFILE or arg == ARG_PRE_LOGFILE:
			_pre_path_helper(arg, res.data, Path(args[0]))
		elif arg == ARG_PRE_DEBUGMODE:
			_arg_helper(res.data, arg, 0)
			res.data[ARG_PRE_DEBUGMODE] = True
		else:
			args.appendleft(arg)
			return

def _do_list(res):
	res.data = ListData()
	if len(args) > 0:
		if args[0] == ARG_VERBOSE:
			res.data.verbose = True
			args.popleft()
	while len(args) > 0:
		arg = args[0]
		args.popleft()
		if verify.backup_id(arg):
			if arg in res.data.entries:
				raise CommandLineError(ERR_DUPLICATE_ARGUMENT.format(arg))
			res.data.entries.append(arg)
		else:
			raise CommandLineError(ERR_INVALID_ARGUMENT.format(arg))
	return res

def _do_run(res):
	res.data = dict()
	while len(args) > 0:
		arg = args[0]
		args.popleft()
		if arg == ARG_NOUMOUNT:
			_arg_helper(res.data, arg, 0)
			res.data[arg] = True
		elif arg == ARG_KEYFILE:
			_arg_helper(res.data, arg, 1)
			p = Path(args[0])
			if not p.is_absolute():
				p = p.resolve()
			try:
				verify.requireExistingPath(p)
			except verify.VerificationError as e:
				raise CommandLineError('Keyfile does not exist: {}'.format(p))
			res.data[arg] = p
			args.popleft()
		elif verify.backup_id(arg):
			if ARG_NAME in res.data:
				raise CommandLineError('The "{}" command supports only one backup name!'.format(ACTION_RUN))
			res.data[ARG_NAME] = arg
		else:
			raise CommandLineError('"{}" is not a valid option for {}'.format(arg, ACTION_RUN))
	if res.data[ARG_NAME] is None:
		raise CommandLineError('The "{}" command needs a backup name!'.format(ACTION_RUN))
	if not ARG_NOUMOUNT in res.data:
		res.data[ARG_NOUMOUNT] = False
	if not ARG_KEYFILE in res.data:
		res.data[ARG_KEYFILE] = None
	return res

def _do_remove(res):
	res.data = list()
	if len(args) == 0:
		raise CommandLineError(ERR_MISSING_ARGUMENT.format(ACTION_REMOVE))
	while len(args) > 0:
		if verify.backup_id(args[0]):
			res.data.append(args[0])
		else:
			raise CommandLineError(ERR_BACKUP_ID.format(args[0]))
		args.popleft()
	return res

def _do_add_modify(res):
	while len(args) > 0:
		arg = args[0]
		args.popleft() #args[0] now points to first parameter
		if arg == ARG_NAME: #id the backup will have
			_arg_helper(res.data, arg, 1)
			if verify.backup_id(args[0]):
				res.data[arg] = args[0]
				args.popleft()
			else:
				raise CommandLineError(ERR_BACKUP_ID.format(args[0]))
		elif arg == ARG_SNAPSHOTS:
			if _arg_optionless(res.data, arg):
				pass
			else:
				_parse_snapshots(arg, res.data)
		elif arg == ARG_TARGET:
			if verify.uuid(args[0]):
				_arg_helper(res.data, arg, 1)
				res.data[arg] = UUID(args[0])
				args.popleft()
			else:
				_parse_arg_with_absolute_path(arg, res.data)
		elif arg == ARG_TARGETDIR: #relative path on the backup drive for the snapshot directory
			if _arg_optionless(res.data, arg):
				pass
			else:
				_arg_helper(res.data, arg, 1)
				td = Path(args[0])
				verify.requireRelativePath(td)
				res.data[arg] = td
				args.popleft()
		elif arg == ARG_SOURCE or arg == ARG_SNAPSHOTDIR or arg == ARG_KEYFILE:
			_parse_arg_with_absolute_path(arg, res.data)
		else:
			raise CommandLineError(ERR_INVALID_ARGUMENT.format(arg))
	return res

def _do_add(res):
	res.data = dict()
	return _do_add_modify(res)
	
def _do_modify(res):
	res.data = dict()
	backupid = args[0]
	args.popleft()
	if not verify.backup_id(backupid):
		raise CommandLineError('Action {}: first argument must be a valid backup name.'.format(ACTION_MODIFY))
	res.data[KEY_BACKUPID] = backupid
	return _do_add_modify(res)

def _do_global(res):
	res.data = dict()
	while len(args) > 0:
		arg = args[0]
		args.popleft() #args[0] now points to first parameter
		if arg == ARG_LOGFILE or arg == ARG_MNT:
			if _arg_optionless(res.data, arg):
				continue
			else:
				_parse_arg_with_absolute_path(arg, res.data)
		elif arg == ARG_LOGLEVEL:
			if _arg_optionless(res.data, arg):
				continue
			else:
				level = args[0]
				if not level in verify.LOGLEVELS:
					raise CommandLineError('"{}" is not a valid log level!'.format(level))
				_arg_helper(res.data, arg, 1)
				res.data[arg] = level
				args.popleft()
		elif arg == ARG_SNAPSHOTS:
			if _arg_optionless(res.data, arg):
				continue
			else:
				_parse_snapshots(arg, res.data)
		else:
			raise CommandLineError(ERR_INVALID_ARGUMENT.format(arg))
	return res

class CommandLineError(Exception):
	def __init__(self, msg = None):
		globalstuff.status = globalstuff.EXIT_COMMANDLINE
		if msg is not None:
			super().__init__(msg)
	pass
