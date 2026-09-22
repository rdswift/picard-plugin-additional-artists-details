"""Entity Definitions for the Additional Artists Details plugin."""

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

from dataclasses import dataclass


class AreaType:
    """Area types"""

    @dataclass
    class AreaTypeData:
        mbid: str
        """MBID of the area type"""

        short_type: str
        """Short (internal) area type code"""

        title: str
        """Title of the area type"""

        conditional: bool
        """Indicator or whether the area type is conditional"""

    COUNTRY = AreaTypeData("06dd0ae4-8c74-30bb-b43d-95dcedf961de", "A", "Country", False)
    SUBDIVISION = AreaTypeData("fd3d44c5-80a1-3842-9745-2c4972d35afa", "B", "Subdivision", True)
    CITY = AreaTypeData("6fd8f29a-3d0a-32fc-980d-ea697b69da78", "C", "City", False)
    MUNICIPALITY = AreaTypeData("17246454-5ac4-36a1-b81a-4753eb2dab20", "D", "Municipality", True)
    DISTRICT = AreaTypeData("84039871-5e47-38ca-a66a-45e512c8290f", "E", "District", False)
    ISLAND = AreaTypeData("3f8e7b66-058b-369b-9834-ffa5fcba5641", "F", "Island", False)
    COUNTY = AreaTypeData("bcecec27-8bdb-3e00-8254-d948dda502fa", "G", "County", True)
    MILITARY_BASE = AreaTypeData("bbb27bc1-f21c-42a9-89ce-e9d986d60b46", "H", "Military base", False)
    INDIGINOUS = AreaTypeData("9bdda430-e4d4-464a-94a9-084a452ea8ea", "I", "Indigenous territory / reserve", False)

    _all_types: list[AreaTypeData] = [
        COUNTRY,
        SUBDIVISION,
        CITY,
        MUNICIPALITY,
        DISTRICT,
        ISLAND,
        COUNTY,
        MILITARY_BASE,
        INDIGINOUS,
    ]

    titles: dict[str, str] = {x.mbid: x.title for x in _all_types}
    """Dictionary of area type titles by MBID"""

    all_mbids: list[str] = [x.mbid for x in _all_types]
    """List of all area type MBIDs"""

    conditional_mbids: list[str] = [x.mbid for x in _all_types if x.conditional]
    """List of all conditional area type MBIDs"""

    unconditional_mbids: list[str] = [x.mbid for x in _all_types if not x.conditional]
    """List of all unconditional area type MBIDs"""

    short_to_type: dict[str, str] = {x.short_type: x.mbid for x in _all_types}
    """Dictionary of MBID type codes by internal short type code"""

    type_to_short: dict[str, str] = {x.mbid: x.short_type for x in _all_types}
    """Dictionary of internal short type codes by MBID type code"""

    @classmethod
    def get_short(cls, code: str) -> str:
        """Get the internal short type code for the specified type MBID.

        Args:
            code (str): MBID area type code to look up.

        Returns:
            str: Internal short area type code.
        """
        return cls.type_to_short.get(code, '')

    @classmethod
    def get_mbid(cls, code: str) -> str:
        """Get the MBID type code for the specified internal short type code.

        Args:
            code (str): Internal short area type code.

        Returns:
            str: MBID area type code.
        """
        return cls.short_to_type.get(code, '')


@dataclass
class ArtistEntity:
    """Represents an artist entity."""

    mbid: str
    """MBID of the artist."""

    name: str
    """Name of the artist."""

    sort: str
    """Sort name of the artist."""

    type: str
    """Type of the artist."""

    gender: str = ''
    """Gender of the artist."""

    area: str = ''
    """MBID of the area of the artist."""

    begin: str = ''
    """Begin date of the artist."""

    begin_area: str = ''
    """MBID of the begin area of the artist."""

    end: str = ''
    """End date of the artist."""

    end_area: str = ''
    """MBID of the end area of the artist."""

    disambiguation: str = ''
    """Disambiguation comment for the artist."""


@dataclass
class AreaEntity:
    """Represents an area entity."""

    mbid: str
    """MBID of the area."""

    name: str
    """Name of the area."""

    type: str = ''
    """MBID of the type of the area."""

    parent: str = ''
    """MBID of the parent of the area."""

    country: str = ''
    """Two-character country code of the area."""
