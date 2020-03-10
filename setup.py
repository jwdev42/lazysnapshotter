from setuptools import setup, find_packages

setup(
		name = 'lazysnapshotter',
		version = '0.3',
		description = 'Frontend for btrfs-subvolume based backups.',
		classifiers = [
			'Development Status :: 3 - Alpha',
			'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
			'Operating System :: POSIX :: Linux',
			'Programming Language :: Python :: 3',
			'Topic :: System :: Archiving :: Backup',
			'Topic :: System :: Systems Administration'
		],
		keywords = 'linux btrfs backup',
		url = 'https://github.com/jwdev42/lazysnapshotter',
		author = 'Jörg Walter',
		author_email = 'jwdev42@posteo.de',
		license = 'GPL-3',
		package_dir = {'': 'src'},
		packages = find_packages('src'),
		scripts=['bin/lazysnapshotter']
)
