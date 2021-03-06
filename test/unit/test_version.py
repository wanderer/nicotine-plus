# COPYRIGHT (C) 2020 Nicotine+ Team
#
# GNU GENERAL PUBLIC LICENSE
#    Version 3, 29 June 2007
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import datetime

from pynicotine.utils import get_latest_version
from pynicotine.utils import make_version
from pynicotine.utils import version


def test_version():

    # Validate local version
    local_version = make_version(version)
    assert type(local_version) is int

    # Validate version of latest release
    latest_version, date = get_latest_version()
    assert type(latest_version) is int

    # Validate date of latest release
    format = "%Y-%m-%dT%H:%M:%SZ"
    datetime.datetime.strptime(date, format)
