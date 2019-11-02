#Name

lazysnapshotter - front end for btrfs subvolume-based backups

#Synopsis

##Command line overview

- lazysnapshotter *\[OPTIONS\]* **global** *\[--logfile FILE\] \[--loglevel LOGLEVEL\] \[--mountdir DIR\]*
- lazysnapshotter *\[OPTIONS\]* **add** *--name BACKUPID --source SUBVOLUME --snapshot-dir DIR --backup-device DEVID \[--backup-dir DIR\] \[--snapshots SNAPSHOTS\] \[--keyfile FILE\]*
- lazysnapshotter *\[OPTIONS\]* **modify** *BACKUPID \[--name BACKUPID\] \[--source SUBVOLUME\] \[--snapshot-dir DIR\] \[--backup-device DEVID\] \[--backup-dir DIR\] \[--snapshots SNAPSHOTS\] \[--keyfile FILE\]*
- lazysnapshotter *\[OPTIONS\]* **remove** *BACKUPID \[BACKUPID\]...*
- lazysnapshotter *\[OPTIONS\]* **list** *\[BACKUPID\]*
- lazysnapshotter *\[OPTIONS\]* **run** *BACKUPID \[--nounmount\] \[--keyfile FILE\]*

##Tokens

- **BACKUPID**: Alphanumeric string that does not begin with a hyphen.
- **DEVID**: Either a path to an existing block device or a UUID.
- **DIR**: Path to an existing directory.
- **FILE**: Path to an existing file.
- **LOGLEVEL**: 'CRITICAL' or 'ERROR' or 'WARNING' or 'INFO' or 'DEBUG'.
- **OPTIONS**: See Description -> Runtime options.
- **SNAPSHOTS**: Integer greater than 0 and less than 256.
- **SUBVOLUME**: Path to the root directory of an existing btrfs subvolume.

#Description

lazysnapshotter simplyfies the backup of btrfs file systems by providing a configuation file to store the parameters for the backup and an algorithm.

##Backup algorithm

1. Optionally decrypt, then mount the backup device to a temporary mount point.
2. Create a new snapshot of SUBVOLUME into snapshot-dir.
3. Find the last common snapshot present in snapshot-dir on the source device and in backup-dir on the backup device.
4. Send the newly created snapshot from snapshot-dir to backup-dir on the backup device. If a common previous snapshot had been found, send the differences between that common snapshot and the new one.
5. Delete old snapshots in snapshot-dir and backup-dir until SNAPSHOTS amount of snapshots are left.
6. Unmount the backup device and unmap its LUKS container if it had one.

##Snapshot specification

Every snapshot created by lazysnapshotter follows a common naming convention:

YYYY-MM-DD.INDEX

INDEX is an integer greater than 0. It is present to distinguish between multiple backups made on the same day. It starts with 1 and is incremented by each snapshot made on the same day.  
Snapshots with the same name are considered equal.

##Runtime options

Runtime options allow specifying custom files or behavior for an instance of lazysnapshotter. Runtime options must be specified before an action.

**--configfile** *FILE*  
Use *FILE* instead of the default configuration file.

**--debug**  
Enable debug mode. This will print a backtrace in case of an error, additionally the loglevel will be set to DEBUG.

**--logfile** *FILE*  
Use *FILE* instead of the default logfile.

**--loglevel** *LOGLEVEL*  
Will override the default loglevel with *LOGLEVEL*. See **Tokens** for a list of valid loglevels.

##Actions
Actions tell the program which task to perform. An action must be specified between the optional runtime options and the action's options. An instance of lazysnapshotter can only perform one action. Valid actions and their options are described below.

###add
Add a new backup entry to the configuration file. The following options can by specified after the action:

**--backup-device** *DEVID*  
Use device *DEVID* as the backup drive. The argument can either be a partition, a loop device or a LUKS container. It is recommended to pass the backup device as a UUID. Mandatory.

**--backup-dir** *DIR*  
The directory where snapshots will be stored on the backup drive, interpreted as a relative path starting at the backup drive's mount point. Optional. If omitted, the backup drive's root directory will be used.

**--keyfile** *FILE*  
Keyfile to open the backup drive if it is encrypted. Optional. A password may be prompted if omitted.

**--name** *BACKUPID*  
Name for the backup. This will act as an ID and must be unique. Alphanumeric characters only, first character must not be a hyphen. Mandatory.

**--snapshot-dir** *DIR*  
The directory for the source snapshots. Must be on the same btrfs file system as the source snapshot. Mandatory.

**--snapshots** *SNAPSHOTS*  
The amount of snapshots this backup should preserve. Optional. If not present, the global or default snapshot amount will be used.

**--source** *SUBVOLUME*  
The btrfs subvolume you want to backup. Mandatory.

###global
Set or change global options for the current configuation file. Valid options:

**--logfile** *FILE*  
Change the default logfile.

**--loglevel** *LOGLEVEL*  
Change the default loglevel. See **tokens** for valid log levels.

**--mountdir** *DIR*  
Set the root directory where lazysnapshotter will create temporary mount points in.

###list
Show a list of all backups in the config file. If a *BACKUPID* is given, the corresponding backup entry will be displayed with all its parameters.

###modify
Modify an existing backup entry. Its *BACKUPID* must be specified directly after the 'modify' action. For valid options see action 'add'. Optional settings can be removed by giving the corresponding command line switch without an argument.

###remove
Remove one or more backup entries.

###run
Run a backup with a given *BACKUPID*. Valid Options:

**--keyfile** *FILE*  
Keyfile to open the backup drive if it is encrypted. Optional. A password may be prompted if omitted.

**--noumount**  
Do not unmount the backup drive after the backup finished. Optional.

#Author
Written by Joerg Walter.

#See also
