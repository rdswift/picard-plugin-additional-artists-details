"""Miscellaneous utility functions for the Additional Artists Details plugin."""

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

import re

from .entities import (
    AreaEntity,
    ArtistEntity,
)


RE_MBID = re.compile(r'^[0-9a-f]{8}-([0-9a-f]{4}-){3}[0-9a-f]{12}$')
RE_COUNTRY_CODE = re.compile(r'^[A-Z]{2}$')


def is_valid_mbid(mbid: str) -> bool:
    """Confirm whether an MBID is of the proper format.

    Args:
        mbid (str): MBID to check.

    Returns:
        bool: True if the MBID matches the proper format, otherwise False.
    """
    return bool(RE_MBID.match(mbid))


def is_valid_country_code(code: str) -> bool:
    """confirm whether a country code is of the proper format.

    Args:
        code (str): Code to check.

    Returns:
        bool: True if the code matches the proper two-character format, otherwise False.
    """
    return bool(RE_COUNTRY_CODE.match(code))


def area_dict_to_entity(mbid: str, info: dict) -> AreaEntity | None:
    if not is_valid_mbid(mbid):
        return None  # Invalid area MBID
    if info is None:
        return None  # Invalid dictionary
    name_: str = str(info.get('name', '')).strip()
    if not name_:
        return None  # Missing name
    type_: str = info.get('type', '')
    if not is_valid_mbid(type_):
        return None  # Invalid area type

    return AreaEntity(
        mbid=mbid,
        name=name_,
        type=type_,
        parent='',
        country=info.get('country', ''),
    )


def artist_dict_to_entity(mbid: str, info: dict) -> ArtistEntity | None:
    if not is_valid_mbid(mbid):
        return None  # Invalid artist MBID
    if info is None:
        return None  # Invalid dictionary
    name_: str = info.get('name', '')
    if not name_.strip():
        return None  # Missing name
    sort_: str = info.get('sort-name', '')
    if not sort_.strip():
        return None  # Missing sort name

    return ArtistEntity(
        mbid=mbid,
        name=name_,
        sort=sort_,
        type=info.get('type', 'Unknown'),
        gender=info.get('gender', '') or '',
        area=(info.get('area', {}) or {}).get('id', ''),
        begin=info.get('life-span', {}).get('begin', '') or '',
        begin_area=(info.get('begin-area', {}) or {}).get('id', ''),
        end=info.get('life-span', {}).get('end', '') or '',
        end_area=(info.get('end-area', {}) or {}).get('id', ''),
        disambiguation=info.get('disambiguation', '') or '',
    )


def artist_entity_to_key_value_pairs(entity: ArtistEntity) -> list[tuple[str, str]]:
    """Get the entity information as a list of key, value pairs.

    Args:
        entity (ArtistEntity): Artist information to process.

    Returns:
        list[tuple[str, str]]: List of key, value tuples.
    """
    return [
        ('id', entity.mbid),
        ('name', entity.name),
        ('sort_name', entity.sort),
        ('type', entity.type),
        ('gender', entity.gender),
        ('area', entity.area),
        ('begin', entity.begin),
        ('begin-area', entity.begin_area),
        ('end', entity.end),
        ('end-area', entity.end_area),
        ('disambiguation', entity.disambiguation),
    ]
