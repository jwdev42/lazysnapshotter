# Copyright 2020 Joerg Walter
# Distributed under the terms of the GNU General Public License v2

EAPI=7

PYTHON_COMPAT=( python3_{9,10} )

inherit distutils-r1 git-r3

DESCRIPTION="Frontend for btrfs-subvolume based backups."
HOMEPAGE="https://github.com/jwdev42/lazysnapshotter"
EGIT_REPO_URI="https://github.com/jwdev42/lazysnapshotter.git"

LICENSE="GPL-3"
SLOT="0"
KEYWORDS=""
IUSE=""

DEPEND=">=sys-fs/btrfs-progs-5.4[python]
				sys-apps/util-linux[python]
				sys-fs/cryptsetup
				virtual/udev"
RDEPEND="${DEPEND}"

RESTRICT="test"

python_install_all() {
	distutils-r1_python_install_all
	#move admin scripts to sbin
	local adminscripts="$(printf %q "${PN}")"
	dodir /usr/sbin
	for script in ${adminscripts}; do
		mv "${ED}/usr/bin/${script}" "${ED}/usr/sbin/${script}" || die "failed moving admin scripts!"
	done
}
