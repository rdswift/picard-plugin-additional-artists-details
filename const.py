"""Constants for the Additional Artists Details plugin."""

# Copyright (C) 2026 Bob Swift (rdswift)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, see <https://www.gnu.org/licenses/>.

import os

from PyQt6.QtCore import QStandardPaths


BASE_FILENAME: str = 'aad_cache'
DB_DIR: str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
DEF_DIR: str = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)
DB_FILE: str = os.path.join(DB_DIR, BASE_FILENAME + '.db')

USER_GUIDE_URL = (
    'https://picard-plugins-user-guides.readthedocs.io/en/latest/additional_artists_details/user_guide.html'
)

# MusicBrainz ID codes for relationship types
RELATIONSHIP_TYPE_PART_OF = 'de7cc874-8b1b-3a05-8272-f3834c968fb7'

DEFAULT_BACKGROUND_PROCESSING_INTERVAL = 60
