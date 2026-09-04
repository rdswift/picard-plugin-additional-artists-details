"""Cache for the Additional Artists Details plugin."""

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

import threading

from .db_utils import DatabaseUtils
from .entities import (
    AreaEntity,
    ArtistEntity,
)


lock = threading.Lock()


# class CacheException(Exception):
#     """Custom exception for the cache"""


class DataCache:
    """Current session cache"""

    area_cache: dict[str, AreaEntity] = {}
    artist_cache: dict[str, ArtistEntity] = {}

    @classmethod
    def set_artist_info(cls, artist_info: ArtistEntity) -> None:
        """Set the artist information in the cache.

        Args:
            artist_info (ArtistEntity): Artist information to store.
        """
        with lock:
            cls.artist_cache[artist_info.mbid] = artist_info

    @classmethod
    def remove_artist_info(cls, artist_id: str) -> None:
        """Remove the specified artist information from the cache.

        Args:
            artist_id (str): MBID of the artist.
        """
        with lock:
            if artist_id in cls.artist_cache:
                del cls.artist_cache[artist_id]

    @classmethod
    def get_artist_info(cls, artist_id: str) -> ArtistEntity | None:
        """Get the dictionary of information for an artist.

        Args:
            artist_id (str): MBID of the artist.

        Returns:
            ArtistEntity: Artist information. None if the artist is not in the cache.
        """
        if artist_id in cls.artist_cache:
            return cls.artist_cache[artist_id]

        entity = DatabaseUtils.get_artist(artist_id)
        if entity is not None:
            # Add to session cache
            cls.set_artist_info(entity)

        return entity

    @classmethod
    def set_area_info(cls, area_info: AreaEntity) -> None:
        """Set the area information in the cache.

        Args:
            area_info (AreaEntity): Area information to store.
        """
        with lock:
            cls.area_cache[area_info.mbid] = area_info

    @classmethod
    def get_area_info(cls, area_id: str) -> AreaEntity | None:
        """Get the information for an area.

        Args:
            area_id (str): MBID of the area.

        Returns:
            AreaEntity: Area information. None if the area is not in the cache.
        """
        if area_id in cls.area_cache:
            return cls.area_cache[area_id]

        entity = DatabaseUtils.get_area(area_id)
        if entity is not None:
            # Add to session cache
            cls.set_area_info(entity)

        return entity
