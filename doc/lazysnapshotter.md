# Name

lazysnapshotter - front end for btrfs subvolume-based backups

# Synopsis

## Command line overview

- lazysnapshotter *\[--configfile FILE\] \[--debug\] \[--logfile FILE\]\[--loglevel LOGLEVEL\]* *ACTION* *\[ACTION_OPTIONS\]*
- lazysnapshotter *\[OPTIONS\]* **global** *\[--logfile FILE\] \[--loglevel LOGLEVEL\] \[--mountdir DIR\] \[--snapshots SNAPSHOTS\]*
- lazysnapshotter *\[OPTIONS\]* **add** *--backup-device DEVID --name BACKUPID --snapshot-dir DIR --source SUBVOLUME \[--backup-dir DIR\] \[--keyfile FILE\] \[--snapshots SNAPSHOTS\]*
- lazysnapshotter *\[OPTIONS\]* **modify** *BACKUPID \[--name BACKUPID\] \[--source SUBVOLUME\] \[--snapshot-dir DIR\] \[--backup-device DEVID\] \[--backup-dir DIR\] \[--snapshots SNAPSHOTS\] \[--keyfile FILE\]*
- lazysnapshotter *\[OPTIONS\]* **remove** *BACKUPID \[BACKUPID\]...*
- lazysnapshotter *\[OPTIONS\]* **list** *\[BACKUPID\]*
- lazysnapshotter *\[OPTIONS\]* **run** *BACKUPID \[--nounmount\] \[--keyfile FILE\]*

## Tokens

- **ACTION**: See Description ➝ Actions.
- **BACKUPID**: Alphanumeric string that does not begin with a hyphen.
- **DEVID**: Either a path to an existing block device or a UUID.
- **DIR**: Path to an existing directory.
- **FILE**: Path to an existing file.
- **LOGLEVEL**: 'CRITICAL' or 'ERROR' or 'WARNING' or 'INFO' or 'DEBUG'.
- **OPTIONS**: See Description ➝ Runtime options.
- **SNAPSHOTS**: Integer greater than 0 and less than 256.
- **SUBVOLUME**: Path to the root directory of an existing btrfs subvolume.

# Description

lazysnapshotter simplyfies the backup of btrfs file systems by running custom backup jobs
defined in a configuration file.

## Features

- Automatic snapshot management.
- Support for encrypted LUKS containers.
- Automatic mounting and unmounting of the backup drive.
- Multiple backup jobs can be defined and run simultaneously.

## Backup process

At first lazysnapshotter reads a specified backup entry from its configuration file,
then it will search for the backup partition (e.g. */dev/sdc3*) specified in that entry.
After a backup partition was found, lazysnapshotter will examine three possibilities:

1. The partition is a LUKS container.
2. The partition is an unmounted file system.
3. The partition is a mounted file system.

If 1 is true, lazysnapshotter will ask for a passphrase in case no keyfile was specified.
The container will be decrypted and mounted afterwards.
In case 2, the file system will be mounted. In case 3, the existing mount point will be used.

After the backup file system was made available lazysnapshotter will compare the
snapshots on the source drive with those on the backup drive.
If a common snapshot is found, a new incremental backup
will be made based on that snapshot. Otherwise a full backup will be started.

A backup in progress will use its backup ID as a temporary name for the newly created snapshots.

If the backup succeeded, it will be comitted by renaming its snapshots.
If the total number of snapshots in a snapshot directory exceeds the defined number of snapshots to be kept,
old snapshots will be deleted until the number of snapshots is within limits again.
The backup partition as well as the LUKS container will be unmounted or closed again
if they were mounted or opened by lazysnapshotter before.

## Actions
Actions tell the program which task to perform. An action must be specified between the optional runtime options and the action's options. An instance of lazysnapshotter can only perform one action. Valid actions and their options are described below.

### add
Add a new backup entry to the configuration file. The following options can by specified after the action:

> **--backup-device** *DEVID*  
> Use device *DEVID* as the backup drive. The argument can either be a partition, a loop device or a LUKS container. It is recommended to pass the backup device as a UUID. Mandatory.

> **--backup-dir** *DIR*  
> The directory where snapshots will be stored on the backup drive, interpreted as a relative path starting at the backup drive's mount point. Optional. If omitted, the backup drive's root directory will be used.

> **--keyfile** *FILE*  
> Keyfile to open the backup drive if it is encrypted. Optional. A password may be prompted if omitted.

> **--name** *BACKUPID*  
> Name for the backup. This will act as an ID and must be unique. Alphanumeric characters only, first character must not be a hyphen. Mandatory.

> **--snapshot-dir** *DIR*  
> The directory for the source snapshots. Must be on the same btrfs file system as the source snapshot. Mandatory.

> **--snapshots** *SNAPSHOTS*  
> The amount of snapshots this backup should preserve. Optional. If not present, the global or default snapshot amount will be used.

> **--source** *SUBVOLUME*  
> The btrfs subvolume you want to backup. Mandatory.

### global
Set or change global options for all backups in the selected configuation file.
You can delete an existing global setting by leaving out its option.
Please note that local options and runtime options have precedence over global options.
Valid options:

> **--logfile** *FILE*  
> Change the default logfile.

> **--loglevel** *LOGLEVEL*  
> Change the default loglevel. See **tokens** for valid log levels.

> **--mountdir** *DIR*
> Set a custom directory where the mount points for the backup drives are created in.

> **--snapshots** *SNAPSHOTS*  
> Set the default amount of snapshots to keep for all backups defined in the current configuration file.

### list
Show a list of all backups in the config file. If a *BACKUPID* is given, the corresponding backup entry will be displayed with all its parameters.

### modify
Modify an existing backup entry. Its *BACKUPID* must be specified directly after the 'modify' action. For valid options see action 'add'. Optional settings can be removed by giving the corresponding command line switch without an argument.

### remove
Remove one or more backup entries.

### run
Run a backup with a given *BACKUPID*. Valid Options:

> **--keyfile** *FILE*  
> Keyfile to open the backup drive if it is encrypted. Optional. A password may be prompted if omitted.

> **--noumount**  
> Do not unmount the backup drive after the backup finished. Optional.

## Runtime options

Runtime options allow specifying custom files or behavior for an instance of lazysnapshotter. Runtime options must be specified before an action.

> **--configfile** *FILE*  
> Use *FILE* instead of the default configuration file.

> **--debug**  
> Enable debug mode. This will print a backtrace in case of an error, additionally the loglevel will be set to DEBUG. The loglevel set by *--debug* will have the highest precedence.

> **--logfile** *FILE*  
> Write the log messages to *FILE* additionally.

> **--loglevel** *LOGLEVEL*  
> Override the default loglevel with *LOGLEVEL*. See **Tokens** for a list of valid loglevels.

## Configuration file

lazysnapshotter's default configuration file is */etc/lazysnapshotter/backups.conf*.
It is advisable to manipulate the configuration file via the lazysnapshotter command only.

## Configuration file format

The configuration file consists of 2 types of entries, one default entry and the desired number of backup entries.
Every entry is initiated by an identifier in square brackets followed by a new line.
An entry's body consists of one or more key-value pairs bound by an equal sign.
Every key-value pair is separated through a new line.  
Example:

	[example]
	backup-device = /dev/sdc2
	snapshot-dir = /mnt/hdd/snapshots
	source = /mnt/hdd/data

### The default entry
The default entry starts with *\[DEFAULT\]* followed by a new line.
Its purpose is the deployment of default options within the scope
of the configuration file.
Valid keys are *logfile*, *loglevel*, *mountdir*, *snapshots*.

> **logfile:** Path to a log file that will be used by all backup jobs defined in this configuration file.  
> Example:  
>
>     logfile = /var/log/important_backups.log

> **loglevel:** Can be used to override lazysnapshotter's default log level for all backup entries in the configuration file.
> Valid values: *CRITICAL*, *ERROR*, *WARNING*, *INFO*, *DEBUG*.  
> Example:
>
>     loglevel = INFO

> **mountdir:** Path to a custom directory that will hold the mount points for all backup jobs in the configuration file.  
> Example:
> 
>     mountdir = /mnt/backups

> **snapshots:** Default amount of preserved snapshots for all backup entries in the configuration file. 
> This will override the default snapshot amount, but not individual values set for specific backup entries.
> Example:
> 
>     snapshots = 3

### The backup entries
A backup entry starts with its name enclosed in square brackets followed by a new line.
Its purpose is the definition of backup jobs.
Valid keys are *backup-device*, *backup-dir*, *keyfile*, *snapshot-dir*, *snapshots*, *source*.

> **backup-device:** UUID for the backup partition.  
> Example:
>
>     backup-device = 8c6bddcf-55d7-46a9-b435-920b220a972f

> **backup-dir:** Relative path to the folder on the backup partition where the backup snapshots will be saved to.
> This declaration is optional.  
> Example:
>
>     backup-dir = data/snapshots

> **keyfile:** Path to a keyfile for the decryption of the backup partition. This declaration is optional.  
> Example:
>
>     keyfile = /etc/privatekey

> **snapshot-dir:** Path to the snapshot directory on the source filesystem.  
> Example:
>
>     snapshot-dir = /mnt/data/snapshots

> **snapshots:** Integer that specifies the amount of snapshots that will be kept.
> This declaration takes precedence over the file-wide and default declarations.  
> Example:
>
>     snapshots = 4

> **source:** Path to the root folder of the subvolume to backup.  
> Example:
>
>     source = /mnt/data/stuff

## Snapshot specification

Every snapshot created by lazysnapshotter follows a common naming convention:

YYYY-MM-DD.I

*I* is an integer greater than 0. It is present for distinction between multiple backups made on the same day.
Snapshots with the same name are considered equal.

## Runtime behaviour

lazysnapshotter's runtime directory is */run/lazysnapshotter*.
Every instance of lazysnapshotter will have its own unique session ID.

### Pid files
Every program instance generates its own PID file under */run/lazysnapshotter/pid/$PID.pid*. 

### Jobs file
The purpose of the jobs file is to prevent the same backup job from
being run simultaneously by different program instances.
The file's location is */run/lazysnapshotter/jobs*, it is shared between
all instances of lazysnapshotter by using a locking mechanism.

### Mount points
The default directory containing backup drive mount points is */run/lazysnapshotter/mounts*.
The mount point itself will be a directory named after the session ID of the current program instance.

# See also

## man pages
- btrfs-send
- btrfs-subvolume
- btrfs-receive

## www

- [btrfs wiki - incremental backup](https://btrfs.wiki.kernel.org/index.php/Incremental_Backup)

# Version
0.3

# Author
Written by Jörg Walter.
