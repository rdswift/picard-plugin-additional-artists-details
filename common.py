"""Common items for the Additional Artists Details plugin."""

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

from picard.plugin3.api import PluginApi

from .const import DEFAULT_BACKGROUND_PROCESSING_INTERVAL
from .translations import TxStrings


class SharedVars:
    """Variables shared between modules"""

    api: PluginApi = None
    """The plugin api used for logging, settings, etc."""

    save_artists: bool = True
    """Indicates whether artists are saved to the cache"""
    use_persistent_cache: bool = True
    """Indicates whether the persistent cache database is used"""

    background_processing_enabled: bool = False
    """Indicates whether background processing is enabled"""
    background_processing_interval: int = DEFAULT_BACKGROUND_PROCESSING_INTERVAL
    """Interval in seconds between background processing tasks"""
    background_processing_running: bool = False
    """Indicates whether background processing is currently running"""

    track_variables_registered: bool = False
    """Indicates whether the track variables have been registered"""

    verbose_log_enabled: bool = False
    """Indicates whether verbose logging is enabled"""


class FileFilters:
    """Standard file filter strings"""

    @classmethod
    def initialize(cls):
        cls.ALL = SharedVars.api.tr(TxStrings.FILTER_ALL) + " (*)"
        cls.CSV = SharedVars.api.tr(TxStrings.FILTER_CSV) + " (*.csv)"
        cls.DB = SharedVars.api.tr(TxStrings.FILTER_DB) + " (*.db)"
        cls.JSON = SharedVars.api.tr(TxStrings.FILTER_JSON) + " (*.json)"
