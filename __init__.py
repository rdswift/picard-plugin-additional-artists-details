"""Additional Artists Details Picard Plugin"""

# Copyright (C) 2023-2026 Bob Swift (rdswift)
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

from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
import os
import threading

from PyQt6 import QtWidgets
from PyQt6.QtCore import (
    QStandardPaths,
    Qt,
    QTimer,
)

from picard.debug_opts import DebugOpt
from picard.plugin3.api import (
    Album,
    BaseAction,
    Metadata,
    OptionsPage,
    PluginApi,
    Track,
    t_,
)

from picard.ui import PicardDialog
from picard.ui.util import FileDialog


# TODO: Remove the following import check when Picard v3.0 is released.
try:
    from picard.util import open_local_path
except ImportError:
    from picard.ui.util import open_local_path
from picard.webservice.api_helpers import MBAPIHelper

from .cache import DataCache
from .common import SharedVars
from .const import (
    BASE_FILENAME,
    DB_DIR,
    DB_FILE,
    DEF_DIR,
    RELATIONSHIP_TYPE_PART_OF,
    USER_GUIDE_URL,
)
from .db_utils import DatabaseUtils
from .entities import (
    AreaEntity,
    AreaType,
)
from .misc_utils import (
    area_dict_to_entity,
    artist_dict_to_entity,
    artist_entity_to_key_value_pairs,
    is_valid_mbid,
)
from .ui_artists_cache_editor import Ui_AdditionalArtistsDetailsCacheEditor
from .ui_cache_status import Ui_AdditionalArtistsDetailsCacheStatus
from .ui_options_additional_artists_details import Ui_AdditionalArtistsDetailsOptionsPage


# Standard text for arguments while parsing MusicBrainz data
ALBUM_ARTISTS = 'album_artists'
ARTIST = 'artist'
ARTIST_REQUESTS = 'artist_requests'
AREA = 'area'
AREA_REQUESTS = 'area_requests'
ISO_CODES_1 = 'iso-3166-1-codes'
ISO_CODES_2 = 'iso-3166-2-codes'
TRACKS = 'tracks'

# Option settings
OPT_AREA_COUNTY = 'area_county'
OPT_AREA_MUNICIPALITY = 'area_municipality'
OPT_AREA_SUBDIVISION = 'area_subdivision'
OPT_PROCESS_TRACKS = 'process_tracks'
OPT_SAVE_ARTISTS_IN_CACHE = 'save_artists_cache'
OPT_USE_CACHE = 'use_cache'
OPT_BACKGROUND_FETCH_AREAS = 'background_fetch'
OPT_BACKGROUND_FETCH_INTERVAL = 'background_fetch_interval'

lock = threading.Lock()


class CustomHelper(MBAPIHelper):
    """Custom MusicBrainz API helper to retrieve artist and area information."""

    def get_artist_by_id(
        self,
        mbid: str,
        handler: Callable,
        inc: list = None,
        priority: bool = False,
        important: bool = False,
        mblogin: bool = False,
        refresh: bool = False,
    ):
        """Get information for the specified artist MBID.

        Args:
            mbid (str): Artist MBID to retrieve.
            handler (Callable): Callback used to process the returned information.
            inc (list, optional): List of includes to add to the API call. Defaults to None.
            priority (bool, optional): Process the request at a high priority. Defaults to False.
            important (bool, optional): Identify the request as important. Defaults to False.
            mblogin (bool, optional): Request requires logging into MusicBrainz. Defaults to False.
            refresh (bool, optional): Request triggers a refresh. Defaults to False.

        Returns:
            PendingRequest: Requested task object.
        """
        return self._get_by_id(
            ARTIST,
            mbid,
            handler,
            inc,
            priority=priority,
            important=important,
            mblogin=mblogin,
            refresh=refresh,
        )

    def get_area_by_id(
        self,
        mbid: str,
        handler: Callable,
        inc: list = None,
        priority: bool = False,
        important: bool = False,
        mblogin: bool = False,
        refresh: bool = False,
    ):
        """Get information for the specified area MBID.

        Args:
            mbid (str): Area MBID to retrieve.
            handler (Callable): Callback used to process the returned information.
            inc (list, optional): List of includes to add to the API call. Defaults to None.
            priority (bool, optional): Process the request at a high priority. Defaults to False.
            important (bool, optional): Identify the request as important. Defaults to False.
            mblogin (bool, optional): Request requires logging into MusicBrainz. Defaults to False.
            refresh (bool, optional): Request triggers a refresh. Defaults to False.

        Returns:
            PendingRequest: Requested task object.
        """
        if inc is None:
            inc = ['area-rels']

        return self._get_by_id(
            AREA,
            mbid,
            handler,
            inc,
            priority=priority,
            important=important,
            mblogin=mblogin,
            refresh=refresh,
        )


@dataclass
class MetadataPair:
    """Track metadata pair"""

    artists: set
    """MBIDs of artists on the track"""

    target: Metadata
    """Track metadata object to update"""


@dataclass
class AreaRelationship:
    """Area relationship information"""

    id: str = ''
    """MBID of the area"""

    name: str = ''
    """Name of the area"""

    type: str = ''
    """MBID type code of the area"""

    type_text: str = ''
    """Text description of the area providing the relationship"""

    direction: str = ''
    """Direction of the relationship"""


class ArtistDetailsPlugin:
    """Plugin to retrieve artist details, including area and country information."""

    cache_requests: dict[str, set] = {
        'artist': set(),
        'area': set(),
    }
    """Dictionary of album and area requests from MusicBrainz"""

    album_processing_count: dict[str, int] = {}
    """Dictionary of number of outstanding requests by album MBID"""

    albums: dict = {}
    """Dictionary of albums being processed"""

    album_area_requests: dict[str, set] = {}
    """Dictionary of the outstanding area requests by album MBID"""

    has_debug_if = False
    """PluginAPI logger supports `debug_if()`"""

    @classmethod
    def _debug_logger(cls, text: str) -> None:
        """Debug logging helper to use `debug_if()` if available.

        Args:
            text (str): Message to log.
        """
        if cls.has_debug_if:
            SharedVars.api.logger.debug_if(DebugOpt.PLUGIN_DEVELOPMENT, text)
        else:
            SharedVars.api.logger.debug(text)

    @classmethod
    def _add_album_area_request(cls, album_id: str, area_id: str) -> None:
        """Add an album area request.

        Args:
            album_id (str): MBID of the album
            area_id (str): MBID of the area
        """
        if album_id not in cls.album_area_requests:
            cls.album_area_requests[album_id] = set()
        cls.album_area_requests[album_id].add(area_id)

    @classmethod
    def _remove_album_area_request(cls, album_id: str, area_id: str) -> None:
        """Remove an album area request.

        Args:
            album_id (str): MBID of the album
            area_id (str): MBID of the area
        """
        if album_id in cls.album_area_requests:
            cls.album_area_requests[album_id].discard(area_id)

    @classmethod
    def _get_album_area_request_count(cls, album_id: str) -> int:
        """Get the count of the current album area requests.

        Args:
            album_id (str): MBID of the album

        Returns:
            int: Number of current requests
        """
        if album_id not in cls.album_area_requests:
            return 0
        return len(cls.album_area_requests[album_id])

    @classmethod
    def _make_empty_target(cls, album_id: str) -> None:
        """Create an empty album target node if it doesn't exist.

        Args:
            album_id (str): MBID of the album.
        """
        if album_id not in cls.albums:
            cls.albums[album_id] = {ALBUM_ARTISTS: set(), TRACKS: []}

    @classmethod
    def _add_target(cls, album_id: str, artists: set, target_metadata: Metadata) -> None:
        """Add a metadata target to update for an album.

        Args:
            album_id (str): MBID of the album.
            artists (set): Set of artists to include.
            target_metadata (Metadata): Target metadata to update.
        """
        cls._make_empty_target(album_id)
        cls.albums[album_id][TRACKS].append(MetadataPair(artists, target_metadata))

    @classmethod
    def _remove_album(cls, album_id: str) -> None:
        """Removes an album from the metadata processing dictionary.

        Args:
            album_id (str): MBID of the album to remove.
        """
        cls._debug_logger(f"Removing album '{album_id}'")
        cls.albums.pop(album_id, None)
        cls.album_processing_count.pop(album_id, None)

    @classmethod
    def _album_add_request(cls, album: Album) -> None:
        """Increment the number of pending requests for an album.

        Args:
            album (Album): The Album object to use for the processing.
        """
        if album.id not in cls.album_processing_count:
            cls.album_processing_count[album.id] = 0
        cls.album_processing_count[album.id] += 1

    @classmethod
    def _album_remove_request(cls, album: Album) -> None:
        """Decrement the number of pending requests for an album.  Trigger
        album finalization if there are no outstanding requests.

        Args:
            album (api.Album): The Album object to use for the processing.
        """
        if album.id not in cls.album_processing_count:
            cls.album_processing_count[album.id] = 1
        cls.album_processing_count[album.id] -= 1

        if cls.album_processing_count[album.id]:
            return

        cls._debug_logger(f"Finalizing loading of album: {album}")
        if cls._save_artist_metadata(album):
            album._finalize_loading(None)

        for count in cls.album_processing_count.values():
            if count:
                return

        # Start / restart orphan area processing
        cls.process_orphan_areas()

    @classmethod
    def remove_album(cls, _api: PluginApi, album: Album) -> None:
        """Remove the album from the albums processing dictionary.

        Args:
            _api (PluginApi): The plugin API object.
            album (Album): The album object to remove.
        """
        cls._remove_album(album.id)

    @classmethod
    def make_album_vars(cls, _api: PluginApi, album: Album, album_metadata, _release_node: dict) -> None:
        """Process album artists.

        Args:
            _api (PluginApi): The plugin API object.
            album (Album): The Album object to use for the processing.
            album_metadata (Metadata): Metadata object for the album.
            _release_metadata (dict): Dictionary of release data from MusicBrainz api.
        """
        cls._debug_logger(f"Processing album: {album.id}")
        artists = set(artist.id for artist in album.get_album_artists())
        cls._make_empty_target(album.id)
        cls.albums[album.id][ALBUM_ARTISTS] = artists

        if not SharedVars.api.plugin_config[OPT_PROCESS_TRACKS]:
            SharedVars.api.logger.info("Track artist processing is disabled.")

        cls._artist_processing(artists, album, album_metadata, 'Album')

    @classmethod
    def _set_track_with_no_artists(cls, track: Track, track_metadata: Metadata) -> None:
        """Set the track metadata using the album artist if no artists identified for the track.

        Args:
            track (Track): Track object to process
            track_metadata (Metadata): Metadata object to update.
        """
        album = track.album
        for artist in cls.albums[album.id][ALBUM_ARTISTS]:
            cls._set_artist_metadata(track_metadata, artist)
        return

    @classmethod
    def make_track_vars(
        cls,
        _api: PluginApi,
        track: Track,
        track_metadata: Metadata,
        track_node: dict,
        _release_node: dict,
    ) -> None:
        """Process track artists.

        Args:
            _api (PluginApi): The plugin API object.
            track (Track): The Track object to use for the processing.
            track_metadata (Metadata): Metadata object for the album.
            track_node (dict): Dictionary of track data from MusicBrainz api.
            _release_node (dict): Dictionary of release data from MusicBrainz api.
        """
        if not SharedVars.api.plugin_config[OPT_PROCESS_TRACKS]:
            cls._set_track_with_no_artists(track, track_metadata)
            return

        artists = set()
        source_type = 'track'
        album = track.album
        # Test for valid metadata node.
        # The 'artist-credit' key should always be there.
        # This check is to avoid a runtime error if it doesn't exist for some reason.
        if 'artist-credit' in track_node:
            for artist_credit in track_node['artist-credit']:
                if 'artist' in artist_credit:
                    if 'id' in artist_credit['artist']:
                        artists.add(artist_credit['artist']['id'])
                else:
                    # No 'artist' specified.  Log as an error.
                    cls._metadata_error(album.id, 'artist-credit.artist', source_type)
        else:
            # No valid metadata found.  Log as error.
            cls._metadata_error(album.id, 'artist-credit', source_type)

        if not artists:
            cls._set_track_with_no_artists(track, track_metadata)
            return

        cls._artist_processing(artists, album, track_metadata, 'Track')

    @classmethod
    def _artist_processing(
        cls,
        artists: set[str],
        album: Album,
        destination_metadata: Metadata,
        source_type: str,
    ) -> None:
        """Retrieves the information for each artist not already processed.

        Args:
            artists (set): Set of artist MBIDs to process.
            album (Album): Album object to use for the processing.
            destination_metadata (Metadata): Metadata object to update with the new variables.
            source_type (str): Source type ('album' or 'track') for logging messages.
        """
        for temp_id in artists:
            if temp_id not in cls.cache_requests['artist'] and DataCache.get_artist_info(temp_id) is None:
                cls.cache_requests['artist'].add(temp_id)
                SharedVars.api.logger.debug('Retrieving artist ID %s information from MusicBrainz.', temp_id)
                cls._get_artist_info(temp_id, album)
            else:
                cls._debug_logger(f"{source_type} artist ID {temp_id} information available from cache.")

        cls._add_target(album.id, artists, destination_metadata)
        cls._save_artist_metadata(album)

    @classmethod
    def _save_artist_metadata(cls, album: Album) -> bool:
        """Saves the new artist details variables to the metadata targets for the specified album.

        Args:
            album (Album): The album to process.
        """
        album_id = album.id

        if album_id in cls.album_processing_count and cls.album_processing_count[album_id]:
            return False

        if cls._get_album_area_request_count(album_id):
            return False

        if album_id not in cls.albums or not cls.albums[album_id][TRACKS]:
            SharedVars.api.logger.error("No metadata targets found for album '%s'", album_id)
            return False

        for item in cls.albums[album_id][TRACKS]:
            item: MetadataPair
            # Add album artists to track so they are available in the metadata
            artists = cls.albums[album_id][ALBUM_ARTISTS].copy().union(item.artists)
            destination_metadata = item.target
            for artist in artists:
                if artist in cls.cache_requests['artist'] or DataCache.get_artist_info(artist) is not None:
                    cls._set_artist_metadata(destination_metadata, artist)

        return True

    @classmethod
    def _set_artist_metadata(cls, destination_metadata: Metadata, artist_id: str) -> None:
        """Adds the artist information to the destination metadata.

        Args:
            destination_metadata (Metadata): Metadata object to update with new variables.
            artist_id (str): MBID of the artist to update.
        """

        def _set_item(key: str, value: str):
            key_ = f"~artist_{artist_id}_{key.replace('-', '_')}"
            destination_metadata[key_] = value

        artist_info = DataCache.get_artist_info(artist_id)

        if artist_info is None:
            return

        for key, value in artist_entity_to_key_value_pairs(artist_info):
            if not value or key == 'id':
                continue

            # if key in {'area', 'begin-area', 'end-area'}:
            if key.endswith('area'):
                country, location = cls._drill_area(value)
                if country:
                    _set_item(key.replace('area', 'country'), country)
                if location:
                    _set_item(key.replace('area', 'location'), location)
            else:
                _set_item(key, value)

    @classmethod
    def _get_artist_info(cls, artist_id: str, album: Album) -> None:
        """Gets the artist information from the MusicBrainz website.

        Args:
            artist_id (str): MBID of the artist to retrieve.
            album (Album): The Album object to use for the processing.
        """
        cls._album_add_request(album)
        task_id = f"Artist={artist_id}"
        helper = CustomHelper(album.tagger.webservice)
        handler = partial(
            cls._artist_submission_handler,
            artist=artist_id,
            album=album,
            task_id=task_id,
        )

        return SharedVars.api.add_album_task(
            album=album,
            task_id=task_id,
            description=f"Get info for artist: {artist_id}",
            timeout=10.0,
            request_factory=lambda: helper.get_artist_by_id(artist_id, handler),
            blocking=True,
        )

    @classmethod
    def _artist_submission_handler(cls, document, _reply, error, artist=None, album=None, task_id=None) -> None:
        """Handles the response from the webservice requests for artist information."""
        if error:
            SharedVars.api.logger.error("Artist '%s' information retrieval error: %s", artist, error)

            # Release task from counter on unrecoverable error.
            SharedVars.api.complete_album_task(album=album, task_id=task_id)
            cls._album_remove_request(album)

            return

        artist_info = artist_dict_to_entity(artist, document)

        if artist_info is None:
            raise ValueError("Invalid information")

        for item in [artist_info.area, artist_info.begin_area, artist_info.end_area]:
            if item:
                cls._queue_ancestors(item, album)

        try:
            DatabaseUtils.set_artist(artist_info)
            DataCache.set_artist_info(artist_info)

        except Exception as ex:
            SharedVars.api.logger.error("Error processing artist '%s' information: %s", artist, ex)

        finally:
            SharedVars.api.complete_album_task(album=album, task_id=task_id)
            cls._album_remove_request(album)

    @classmethod
    def _queue_ancestors(cls, area_id: str, album: Album) -> None:
        """Queues the ancestor areas for processing.

        Args:
            area_id (str): MBID of the area to retrieve.
            album (Album): The Album object to use for the processing.
        """

        while area_id:
            if not area_id:
                # No area ID to process.  Break out of the loop.
                break

            if area_id in cls.cache_requests['area']:
                # Area ID already queued for processing.  Break out of the loop.
                break

            area_info = DataCache.get_area_info(area_id)
            if area_info is None:
                # Area ID not in the cache.  Queue it for processing and break out of the loop.
                cls._get_area_info(area_id, album)
                break

            area_id = area_info.parent

    @classmethod
    def _get_area_info(cls, area_id: str, album: Album) -> None:
        """Gets the area information from the MusicBrainz website.

        Args:
            area_id (str): MBID of the area to retrieve.
            album (Album): The Album object to use for the processing.
        """
        task_id = f"Area={area_id}"
        cls.cache_requests['area'].add(area_id)
        cls._album_add_request(album)
        cls._add_album_area_request(album.id, area_id)
        SharedVars.api.logger.debug('Retrieving area ID %s from MusicBrainz.', area_id)
        helper = CustomHelper(album.tagger.webservice)
        handler = partial(
            cls._area_submission_handler,
            area=area_id,
            album=album,
            task_id=task_id,
        )

        return SharedVars.api.add_album_task(
            album=album,
            task_id=task_id,
            description=f"Get info for area: {area_id}",
            timeout=10.0,
            request_factory=lambda: helper.get_area_by_id(area_id, handler),
            blocking=True,
        )

    @classmethod
    def _area_submission_handler(cls, document, _reply, error, area=None, album=None, task_id=None) -> None:
        """Handles the response from the webservice requests for area information."""
        if error:
            SharedVars.api.logger.error("Area '%s' information retrieval error.", area)

            # Release task from counter on unrecoverable error.
            SharedVars.api.complete_album_task(album=album, task_id=task_id)
            cls._remove_album_area_request(album.id, area)
            cls._album_remove_request(album)

            return

        info = cls._parse_area(document)
        new_id = info.get('id', '')
        area_info = area_dict_to_entity(new_id, info)

        if not info or not new_id or area_info is None:
            SharedVars.api.logger.error("Area '%s' information invalid.", area)

            # Release task from counter on unrecoverable error.
            SharedVars.api.complete_album_task(album=album, task_id=task_id)
            cls._remove_album_area_request(album.id, area)
            cls._album_remove_request(album)

            return

        parent_id = '' if info['type'] == AreaType.COUNTRY.mbid else cls._get_area_parent(document)
        area_info.parent = parent_id

        cls._area_logger(
            area_id=new_id,
            area_name=area_info.name,
            area_type=AreaType.titles.get(area_info.type, 'Unknown'),
        )

        try:
            DatabaseUtils.set_area(area_info)
            DataCache.set_area_info(area_info)

            for rel in document.get('relations', []):
                area_rel = cls._parse_area_forward_relationship(rel)
                if area_rel is None or not is_valid_mbid(area_rel.id):
                    continue

                area_info = AreaEntity(
                    mbid=area_rel.id,
                    name=area_rel.name,
                    type=area_rel.type,
                    parent=new_id,
                    country='',
                )

                cls._area_logger(
                    area_id=area_info.mbid,
                    area_name=area_info.name,
                    area_type=AreaType.titles.get(area_info.type, 'Unknown'),
                )

                DatabaseUtils.set_area(area_info)
                DataCache.set_area_info(area_info)

            # Set up requests for missing ancestors as required
            cls._queue_ancestors(parent_id, album)

        except Exception as ex:
            SharedVars.api.logger.error("Error processing area '%s' information: %s", area, ex)

        finally:
            SharedVars.api.complete_album_task(album=album, task_id=task_id)
            cls._remove_album_area_request(album.id, area)
            cls._album_remove_request(album)

    @staticmethod
    def _get_area_parent(document: dict) -> str:
        """Get the parent area ID for a given area document.

        Args:
            document (dict): The area document.

        Returns:
            str: The parent area ID.
        """
        parent = ''
        relations = document.get('relations', [])
        for rel in relations:
            if (
                rel.get('type-id', '') == RELATIONSHIP_TYPE_PART_OF
                and rel.get('direction', '') == 'backward'
                and not rel.get('ended', False)
            ):
                parent = rel.get('area', {}).get('id', '')
                if parent:
                    break
        return parent

    @classmethod
    def _area_logger(cls, area_id: str, area_name: str, area_type: str) -> None:
        """Adds a log entry for the area retrieved.

        Args:
            area_id (str): MBID of the area added.
            area_name (str): Name of the area added.
            area_type (str): Type of area added.
        """
        cls._debug_logger(f"Adding area: {area_id} => \"{area_name}\" of type '{area_type}'")

    @classmethod
    def _parse_area_forward_relationship(cls, area_relation: dict) -> AreaRelationship | None:
        """Parse an area relation to extract the forward area relationship information.

        Args:
            area_relation (dict): Dictionary of the area relationship.

        Returns:
            AreaRelationship: Area relationship information or None if invalid relationship.
        """
        rel_type = area_relation.get('type-id', '')
        rel_direction = area_relation.get('direction', '')
        if rel_type != RELATIONSHIP_TYPE_PART_OF or rel_direction != 'forward':
            return None
        area_info = cls._parse_area(area_relation.get('area', {}))
        if not area_info or not area_info.get('id', ''):
            return None
        return AreaRelationship(
            id=area_info.get('id', ''),
            name=area_info.get('name', ''),
            type=area_info.get('type', ''),
            type_text=area_info.get('type_text', ''),
            direction=rel_direction,
        )

    @staticmethod
    def _parse_area(area_info: dict) -> dict[str, str]:
        """Parse a dictionary of area information to return selected elements.

        Args:
            area_info (dict): Area information to parse.

        Returns:
            dict[str, str]: Selected information for the area (id, name, country code, type code, type text).
        """
        if 'id' not in area_info:
            return {}

        area_id = area_info['id']
        area_name = area_info.get('name', 'Unknown Name')
        area_type = area_info.get('type-id', '')
        area_type_text = area_info.get('type', 'Unknown Area Type')
        country = ''

        if area_type == AreaType.COUNTRY.mbid:
            if ISO_CODES_1 in area_info and area_info[ISO_CODES_1]:
                country = area_info[ISO_CODES_1][0]
            elif ISO_CODES_2 in area_info and area_info[ISO_CODES_2]:
                country = area_info[ISO_CODES_2][0][:2]

        return {'id': area_id, 'name': area_name, 'country': country, 'type': area_type, 'type_text': area_type_text}

    @classmethod
    def _metadata_error(cls, album_id: str, metadata_element: str, metadata_group: str) -> None:
        """Logs metadata-related errors.

        Args:
            album_id (str): MBID of the album being processed.
            metadata_element (str): Metadata element initiating the error.
            metadata_group (str): Metadata group initiating the error.
        """
        SharedVars.api.logger.error(
            "Album '%s' missing '%s' in %s metadata.", album_id, metadata_element, metadata_group
        )

    @classmethod
    def _drill_area(cls, area_id: str) -> tuple[str, str]:
        """Drills up from the specified area to determine the two-character
        country code and the full location description for the area.

        Args:
            area_id (str): MBID of the area to process.

        Returns:
            tuple: The two-character country code and full location description for the area.
        """
        country = ''
        location = []
        i = 7  # Counter to avoid potential runaway processing

        while i and area_id and not country:
            i -= 1
            area = DataCache.get_area_info(area_id)

            if area is None:
                continue

            country = area.country
            area_id = area.parent

            if not location or area.type not in AreaType.conditional_mbids:
                location.append(area.name)
            else:
                if (
                    (area.type == AreaType.COUNTY.mbid and SharedVars.api.plugin_config[OPT_AREA_COUNTY])
                    or (area.type == AreaType.MUNICIPALITY.mbid and SharedVars.api.plugin_config[OPT_AREA_MUNICIPALITY])
                    or (area.type == AreaType.SUBDIVISION.mbid and SharedVars.api.plugin_config[OPT_AREA_SUBDIVISION])
                ):
                    location.append(area.name)

        return country, ', '.join(location)

    @classmethod
    def process_orphan_areas(cls) -> None:
        """Retrieve missing area parents in the background."""
        text = "Background processing halted."
        if not SharedVars.use_persistent_cache:
            SharedVars.api.logger.debug("Persistent cache disabled. " + text)
            SharedVars.background_processing_running = False
            return

        if not SharedVars.background_processing_enabled:
            SharedVars.api.logger.debug("Background processing disabled. " + text)
            SharedVars.background_processing_running = False
            return

        if DatabaseUtils.get_orphan_areas_count()[0] < 1:
            SharedVars.api.logger.debug("No orphan area records found. " + text)
            SharedVars.background_processing_running = False
            return

        SharedVars.background_processing_running = True
        for area in DatabaseUtils.get_missing_parent_areas():
            QTimer.singleShot(
                SharedVars.background_processing_interval * 1000,
                partial(cls._get_single_area_info, area_id=area),
            )
            # Only queue one item at a time.
            break

    @classmethod
    def _get_single_area_info(cls, area_id: str) -> None:
        """Gets the area information from the MusicBrainz website for a single area.

        Args:
            area_id (str): MBID of the area to retrieve.
        """
        helper = CustomHelper(SharedVars.api.tagger.webservice)
        SharedVars.api.logger.debug('Retrieving area ID %s from MusicBrainz as a background task.', area_id)
        handler = partial(
            cls._single_area_submission_handler,
            area=area_id,
        )
        helper.get_area_by_id(area_id, handler)

    @classmethod
    def _single_area_submission_handler(cls, document, _reply, error, area=None) -> None:
        if error:
            SharedVars.api.logger.error("Area '%s' information retrieval error.  Background processing halted.", area)
            SharedVars.background_processing_running = False
            return

        SharedVars.api.logger.debug('Retrieved area ID %s from MusicBrainz.', area)

        info = cls._parse_area(document)
        new_id = info.get('id', '')
        area_info = area_dict_to_entity(new_id, info)

        if not info or not new_id or new_id != area or area_info is None:
            SharedVars.api.logger.error("Area '%s' information invalid.  Background processing halted.", area)
            SharedVars.background_processing_running = False
            return

        parent_id = '' if info['type'] == AreaType.COUNTRY.mbid else cls._get_area_parent(document)
        area_info.parent = parent_id

        cls._area_logger(
            area_id=new_id,
            area_name=area_info.name,
            area_type=AreaType.titles.get(area_info.type, 'Unknown'),
        )

        try:
            DatabaseUtils.set_area(area_info)
            DataCache.set_area_info(area_info)

            for rel in document.get('relations', []):
                area_rel = cls._parse_area_forward_relationship(rel)
                if area_rel is None or not is_valid_mbid(area_rel.id):
                    continue

                area_info = AreaEntity(
                    mbid=area_rel.id,
                    name=area_rel.name,
                    type=area_rel.type,
                    parent=new_id,
                    country='',
                )

                cls._area_logger(
                    area_id=area_info.mbid,
                    area_name=area_info.name,
                    area_type=AreaType.titles.get(area_info.type, 'Unknown'),
                )

                DatabaseUtils.set_area(area_info)
                DataCache.set_area_info(area_info)

        except Exception as ex:
            SharedVars.api.logger.error("Error processing area '%s' information: %s", area, ex)
            return

        # Set up requests for missing ancestors as required
        cls.process_orphan_areas()


class AdditionalArtistsDetailsOptionsPage(OptionsPage):
    """Options page for the Additional Artists Details plugin."""

    TITLE = t_("ui.title", "Additional Artists Details")
    HELP_URL = USER_GUIDE_URL

    _DELETE_CONFIRMATION_MSG_TITLE = t_('ui.delete.confirmation.title', "Confirm Database Deletion")
    _DELETE_CONFIRMATION_MSG_TEXT = t_(
        key='ui.delete.confirmation.message',
        text=(
            "You are about to delete the local persistent cache database file from your system. "
            "There is no way to undo this action.  Continue?"
        ),
    )
    _DELETE_SUCCESS_TEXT = t_(
        key='ui.delete.success.message',
        text="The persistent cache database file has been successfully deleted.",
    )
    _DELETE_RESULT_TITLE = t_('ui.delete.result.title', "Delete Database")
    _DELETE_ERROR_TEXT = t_(
        key='ui.delete.error.message',
        text="There was a problem deleting the persistent cache database file.\n\nError: %s",
    )
    _ERR_MSG_TITLE = t_('ui.error.cache_title', "Cache Error")
    _ERR_MSG_CACHE_IMPORT = t_('ui.error.cache_import', "Error importing the cache file.\nFile: %s\n\n%s")
    _ERR_MSG_CACHE_EXPORT = t_('ui.error.cache_export', "Error exporting the cache file.\nFile: %s\n\n%s")
    _SUCCESS_IMPORT = t_('ui.success.import', "Successfully imported the cache file.\nFile: %s")
    _SUCCESS_EXPORT = t_('ui.success.export', "Successfully exported the cache file.\nFile: %s")
    _FILTER_ALL = t_('ui.filter.all', "All files")
    _FILTER_CSV = t_('ui.filter.csv', "CSV files")
    _FILTER_JSON = t_('ui.filter.json', "JSON files")

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.ui = Ui_AdditionalArtistsDetailsOptionsPage()
        self.ui.setupUi(self)

        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon)
        self.ui.b_open_cache_directory.setIcon(icon)

        self.ui.b_open_cache_directory.clicked.connect(self.open_cache_directory)
        self.ui.b_edit_cache.clicked.connect(self.cache_edit)
        self.ui.b_import_cache.clicked.connect(self.cache_import)
        self.ui.b_export_cache.clicked.connect(self.cache_export)
        self.ui.b_delete_cache.clicked.connect(self.cache_delete)
        self.ui.b_cache_status.clicked.connect(self.cache_status)

        self.ui.cb_use_cache.stateChanged.connect(self._use_cache_state_changed)
        self.ui.cb_save_artists.stateChanged.connect(self._save_artists_state_changed)

        self.ui.cache_file.setText(DB_FILE)

        self.filter_all = SharedVars.api.tr(self._FILTER_ALL) + " (*)"
        self.filter_csv = SharedVars.api.tr(self._FILTER_CSV) + " (*.csv)"
        self.filter_json = SharedVars.api.tr(self._FILTER_JSON) + " (*.json)"

        self.user_documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)

    def load(self) -> None:
        """Load the option settings."""
        self.ui.cb_process_tracks.setChecked(SharedVars.api.plugin_config[OPT_PROCESS_TRACKS])
        self.ui.cb_area_county.setChecked(SharedVars.api.plugin_config[OPT_AREA_COUNTY])
        self.ui.cb_area_municipality.setChecked(SharedVars.api.plugin_config[OPT_AREA_MUNICIPALITY])
        self.ui.cb_area_subdivision.setChecked(SharedVars.api.plugin_config[OPT_AREA_SUBDIVISION])
        self.ui.cb_use_cache.setChecked(SharedVars.api.plugin_config[OPT_USE_CACHE])
        self.save_artists = SharedVars.api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE]
        self.ui.cb_save_artists.setChecked(self.save_artists)
        self.ui.cb_use_background_processing.setChecked(SharedVars.api.plugin_config[OPT_BACKGROUND_FETCH_AREAS])
        self.ui.background_processing_interval.setValue(SharedVars.api.plugin_config[OPT_BACKGROUND_FETCH_INTERVAL])
        self._set_button_states()

    def save(self) -> None:
        """Save the option settings."""
        SharedVars.api.plugin_config[OPT_PROCESS_TRACKS] = self.ui.cb_process_tracks.isChecked()
        SharedVars.api.plugin_config[OPT_AREA_COUNTY] = self.ui.cb_area_county.isChecked()
        SharedVars.api.plugin_config[OPT_AREA_MUNICIPALITY] = self.ui.cb_area_municipality.isChecked()
        SharedVars.api.plugin_config[OPT_AREA_SUBDIVISION] = self.ui.cb_area_subdivision.isChecked()
        SharedVars.use_persistent_cache = self.ui.cb_use_cache.isChecked()
        SharedVars.api.plugin_config[OPT_USE_CACHE] = SharedVars.use_persistent_cache
        SharedVars.save_artists = self.ui.cb_save_artists.isChecked()
        SharedVars.api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE] = SharedVars.save_artists
        self.save_artists = SharedVars.save_artists
        SharedVars.api.plugin_config[OPT_BACKGROUND_FETCH_AREAS] = self.ui.cb_use_background_processing.isChecked()
        SharedVars.api.plugin_config[OPT_BACKGROUND_FETCH_INTERVAL] = self.ui.background_processing_interval.value()
        if SharedVars.use_persistent_cache:
            initialize_cache_db()

    def _save_artists_state_changed(self) -> None:
        self._set_button_states()

    def _use_cache_state_changed(self) -> None:
        self._set_button_states()

    def _set_button_states(self) -> None:
        cache_exists = os.path.isfile(DB_FILE)
        enabled = self.ui.cb_use_cache.isChecked()

        self.ui.b_edit_cache.setEnabled(cache_exists and enabled and self.ui.cb_save_artists.isChecked())
        self.ui.b_import_cache.setEnabled(cache_exists and enabled)
        self.ui.b_export_cache.setEnabled(cache_exists and enabled)
        self.ui.b_delete_cache.setEnabled(cache_exists and not enabled)

    def cache_import(self) -> None:
        """Import from a cache file."""
        filepath, filter = FileDialog.getOpenFileName(
            parent=self,
            directory=DEF_DIR,
            # filter=self.filter_csv + ";;" + self.filter_json + ";;" + self.filter_all,
            filter=self.filter_csv + ";;" + self.filter_json,
            initialFilter=self.filter_csv,
        )

        if not filepath:
            return

        if filter == self.filter_json:
            importer = DatabaseUtils.import_from_json
        else:
            importer = DatabaseUtils.import_from_csv

        try:
            importer(filename=filepath, save_artists=self.ui.cb_save_artists.isChecked())
            QtWidgets.QMessageBox.information(self, None, SharedVars.api.tr(self._SUCCESS_IMPORT) % (filepath,))
        except Exception as ex:
            SharedVars.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                SharedVars.api.tr(self._ERR_MSG_TITLE),
                SharedVars.api.tr(self._ERR_MSG_CACHE_IMPORT)
                % (
                    filepath,
                    ex,
                ),
            )

    def cache_export(self) -> None:
        """Export to a cache file."""
        filepath, _filter = FileDialog.getSaveFileName(
            parent=self,
            directory=os.path.join(DEF_DIR, BASE_FILENAME + '.csv'),
            # filter=self.filter_csv + ";;" + self.filter_all,
            filter=self.filter_csv,
            initialFilter=self.filter_csv,
        )
        if not filepath:
            return

        try:
            DatabaseUtils.export_to_csv(filename=filepath, save_artists=self.ui.cb_save_artists.isChecked())
            QtWidgets.QMessageBox.information(self, None, SharedVars.api.tr(self._SUCCESS_EXPORT) % (filepath,))
        except Exception as ex:
            SharedVars.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                SharedVars.api.tr(self._ERR_MSG_TITLE),
                SharedVars.api.tr(self._ERR_MSG_CACHE_EXPORT)
                % (
                    filepath,
                    ex,
                ),
            )

    def cache_edit(self) -> None:
        """Edit the artists retained in the session cache and database file."""
        editor = CacheEditorPage(self)
        editor.exec()

    def cache_status(self) -> None:
        """Display the status of the session cache and database file."""
        page = CacheStatusPage(self)
        page.exec()

    def cache_delete(self) -> bool:
        if (
            QtWidgets.QMessageBox.warning(
                self,
                SharedVars.api.tr(self._DELETE_CONFIRMATION_MSG_TITLE),
                SharedVars.api.tr(self._DELETE_CONFIRMATION_MSG_TEXT),
                QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            == QtWidgets.QMessageBox.StandardButton.Cancel
        ):
            return False

        try:
            os.remove(DB_FILE)

            QtWidgets.QMessageBox.information(
                self,
                SharedVars.api.tr(self._DELETE_RESULT_TITLE),
                SharedVars.api.tr(self._DELETE_SUCCESS_TEXT),
            )

        except OSError as e:
            QtWidgets.QMessageBox.critical(
                self,
                SharedVars.api.tr(self._DELETE_RESULT_TITLE),
                SharedVars.api.tr(self._DELETE_ERROR_TEXT) % e,
            )
            return False

        finally:
            self._set_button_states()

        return True

    def open_cache_directory(self) -> None:
        """Open the persistent cache file directory in system file browser."""
        open_local_path(DB_DIR)


class CacheStatusPage(PicardDialog):
    """Cache Status Dialog"""

    _CACHE_MISSING_TEXT = t_(
        key='ui.not_found.message',
        text="Note: The cache database was not found.",
    )

    _ORPHANS_MSG_TEXT = t_(
        key='ui.orphans.message', text="There are orphan area records. Missing parents: %s, Orphan areas: %s"
    )

    _NO_ORPHANS_MSG_TEXT = t_(key='ui.no_orphans.message', text="There are no orphan area records.")

    _BACKGROUND_RUNNING_MSG_TEXT = t_(
        key='ui.background_running.message', text="Background processing is currently running."
    )

    _BACKGROUND_NOT_RUNNING_MSG_TEXT = t_(
        key='ui.background_not_running.message', text="Background processing is currently not running."
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.ui = Ui_AdditionalArtistsDetailsCacheStatus()
        self.ui.setupUi(self)

        self.ui.buttonBox.accepted.connect(self.close)
        self.ui.buttonBox.rejected.connect(self.close)

        # Set database cache counts in display
        if os.path.exists(DB_FILE) and os.path.isfile(DB_FILE):
            (artist, area) = DatabaseUtils.get_counts()
            parents, children = DatabaseUtils.get_orphan_areas_count()
            if parents > 0:
                text = SharedVars.api.tr(self._ORPHANS_MSG_TEXT) % (parents, children)
                if SharedVars.background_processing_running:
                    text += '\n' + SharedVars.api.tr(self._BACKGROUND_RUNNING_MSG_TEXT)
                else:
                    text += '\n' + SharedVars.api.tr(self._BACKGROUND_NOT_RUNNING_MSG_TEXT)
                self.ui.status_note.setText(text)
            else:
                self.ui.status_note.setText(SharedVars.api.tr(self._NO_ORPHANS_MSG_TEXT))
        else:
            self.ui.status_note.setText(SharedVars.api.tr(self._CACHE_MISSING_TEXT))
            (artist, area) = (None, None)

        self.ui.database_artists_count.setText('n/a' if artist is None else f"{artist:,}")
        self.ui.database_areas_count.setText('n/a' if area is None else f"{area:,}")

        # Set session cache counts in display
        self.ui.session_artists_count.setText(f"{len(DataCache.artist_cache):,}")
        self.ui.session_areas_count.setText(f"{len(DataCache.area_cache):,}")


class CacheEditorPage(PicardDialog):
    """Cache Editor Dialog"""

    _CONFIRMATION_MSG_TITLE = t_('ui.remove.confirmation.title', "Confirm Removal")
    _CONFIRMATION_MSG_TEXT = t_(
        key='ui.remove.confirmation.message',
        text="You are about to remove {n} artist record from the cache.  Continue?",
        plural="You are about to remove {n} artist records from the cache.  Continue?",
    )
    _SUCCESS_MSG_TITLE = t_('ui.remove.success.title', "Artist Removal Success")
    _SUCCESS_MSG_TEXT = t_(
        key='ui.remove.success.message',
        text="Artist removal from the cache successfully completed.",
    )
    _FILTER_STATUS_UNFILTERED = t_('ui.filter_status.unfiltered', "(unfiltered)")
    _FILTER_STATUS_FILTERED = t_(
        key='ui.filter_status.filtered',
        text="({n} item)",
        plural="({n} items)",
    )
    _NO_ARTISTS_TITLE = t_('ui.no_artists.title', "No Artists")
    _NO_ARTISTS_TEXT = t_(
        key='ui.no_artists.message',
        text="There were no artists found in the cache.  The editor will now close.",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.ui = Ui_AdditionalArtistsDetailsCacheEditor()
        self.ui.setupUi(self)

        self.matched_items = []

        icon_up = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarShadeButton)
        icon_dn = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_TitleBarUnshadeButton)
        self.ui.b_filter_previous.setIcon(icon_up)
        self.ui.b_filter_next.setIcon(icon_dn)

        self.ui.filter_text.setText("")
        self._update_filter_status()

        self.ui.cb_select_all.clicked.connect(self.selector_clicked)
        self.ui.b_remove.clicked.connect(self.remove_artists)
        self.ui.b_cancel.clicked.connect(self.close)

        self.ui.listWidget.itemChanged.connect(self.list_item_changed)
        self.ui.listWidget.currentRowChanged.connect(self._set_up_down_states)

        self.ui.filter_text.textChanged.connect(self.filter_changed)
        self.ui.b_filter_previous.clicked.connect(self.move_up)
        self.ui.b_filter_next.clicked.connect(self.move_down)

        self.load_artists()
        self.update_checked_selector_state()

        # Check and display dialog after delay to ensure editor page is visible
        QTimer.singleShot(10, self._check_if_no_artists)

    def load_artists(self) -> None:
        """Load the list of artists from the cache."""
        self.ui.listWidget.clear()
        for artist in DatabaseUtils.get_all_artists():
            item = QtWidgets.QListWidgetItem(f"{artist.sort} [{artist.type}]")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, artist.mbid)
            self.ui.listWidget.addItem(item)

        if self.ui.listWidget.count() < 1:
            return

        self.current_item = self.ui.listWidget.item(0)

        # Initialize the normal and bold font definitions
        self.font_normal = self.current_item.font()
        self.font_bold = self.current_item.font()
        self.font_bold.setBold(True)

        self._set_up_down_states()

    def _update_filter_status(self) -> None:
        """Display count of filtered items."""
        if self.ui.filter_text.text():
            self.ui.filter_status_label.setText(
                SharedVars.api.trn(*self._FILTER_STATUS_FILTERED, n=len(self.matched_items))
            )
        else:
            self.ui.filter_status_label.setText(SharedVars.api.tr(self._FILTER_STATUS_UNFILTERED))

    def filter_changed(self) -> None:
        """Process updated filter string."""
        if self.ui.filter_text.text():
            self.matched_items = self.ui.listWidget.findItems(self.ui.filter_text.text(), Qt.MatchFlag.MatchContains)
        else:
            self.matched_items = []
        self._update_filter_status()

        if self.matched_items:
            self.ui.listWidget.setCurrentItem(self.matched_items[0])
        else:
            self.ui.listWidget.setCurrentRow(0)
        self.current_item = self.ui.listWidget.currentItem()

        for index in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(index)
            if item in self.matched_items:
                item.setFont(self.font_bold)
            else:
                item.setFont(self.font_normal)

        self.ui.b_filter_previous.setEnabled(False)
        self.ui.b_filter_next.setEnabled(len(self.matched_items) > 1)

    def move_up(self) -> None:
        """Move current item to the previous filtered item."""
        current_index = self.ui.listWidget.currentRow()
        new_item = self.ui.listWidget.item(0)
        for item in reversed(self.matched_items):
            try:
                idx = self.ui.listWidget.row(item)
                if idx < current_index:
                    new_item = item
                    break
            except ValueError:
                continue
        self._move_current_item(new_item)

    def move_down(self) -> None:
        """Move current item to the next filtered item."""
        current_index = self.ui.listWidget.currentRow()
        new_item = self.ui.listWidget.item(self.ui.listWidget.count() - 1)
        for item in self.matched_items:
            try:
                idx = self.ui.listWidget.row(item)
                if idx > current_index:
                    new_item = item
                    break
            except ValueError:
                continue
        self._move_current_item(new_item)

    def _move_current_item(self, item: QtWidgets.QListWidgetItem) -> None:
        """Set the current item in the list.

        Args:
            item (QtWidgets.QListWidgetItem): Item to make current.
        """
        self.ui.listWidget.setCurrentItem(item)
        self._set_up_down_states()

    def _set_up_down_states(self) -> None:
        """Set the enabled states for the up and down buttons."""
        if not self.matched_items:
            self.ui.b_filter_previous.setEnabled(False)
            self.ui.b_filter_next.setEnabled(False)
        else:
            current_index = self.ui.listWidget.currentRow()
            first_index = self.ui.listWidget.row(self.matched_items[0])
            last_index = self.ui.listWidget.row(self.matched_items[-1])
            self.ui.b_filter_previous.setEnabled(current_index > first_index)
            self.ui.b_filter_next.setEnabled(current_index < last_index)

    def list_item_changed(self, _item: QtWidgets.QListWidgetItem) -> None:
        """Process when the current item has been checked or unchecked."""
        self.update_checked_selector_state()

    def remove_artists(self) -> None:
        """Remove the selected artists from the cache, display a results dialog and exit."""
        count = self.get_checked_count()
        if count < 1:
            return

        if (
            QtWidgets.QMessageBox.warning(
                self,
                SharedVars.api.tr(self._CONFIRMATION_MSG_TITLE),
                SharedVars.api.trn(*self._CONFIRMATION_MSG_TEXT, n=count),
                QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel,
                QtWidgets.QMessageBox.StandardButton.Cancel,
            )
            == QtWidgets.QMessageBox.StandardButton.Cancel
        ):
            return

        artists = []
        for index in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                mbid = item.data(Qt.ItemDataRole.UserRole)
                DataCache.remove_artist_info(mbid)
                artists.append(mbid)

        DatabaseUtils.remove_artists(artists)

        QtWidgets.QMessageBox.information(
            self,
            SharedVars.api.tr(self._SUCCESS_MSG_TITLE),
            SharedVars.api.tr(self._SUCCESS_MSG_TEXT),
        )

        self.close()

    def get_checked_count(self) -> int:
        """Get the number of checked items in the list."""
        count = 0
        for index in range(self.ui.listWidget.count()):
            if self.ui.listWidget.item(index).checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def selector_clicked(self) -> None:
        """Select or deselect all items when master selector checkbox is clicked."""
        total = self.ui.listWidget.count()
        count = self.get_checked_count()
        set_state = Qt.CheckState.Checked if count < total else Qt.CheckState.Unchecked
        for index in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(index)
            item.setCheckState(set_state)
        count = total if set_state == Qt.CheckState.Checked else 0
        self.ui.checked_count_label.setText(f"({count:,}/{total:,})")
        self.ui.cb_select_all.setCheckState(set_state)
        self.ui.b_remove.setEnabled(count > 0)

    def update_checked_selector_state(self) -> None:
        """Update the display state of the master selector checkbox."""
        total = self.ui.listWidget.count()
        count = self.get_checked_count()
        self.ui.checked_count_label.setText(f"({count:,}/{total:,})")
        if count < 1:
            self.ui.cb_select_all.setCheckState(Qt.CheckState.Unchecked)
        elif count >= total:
            self.ui.cb_select_all.setCheckState(Qt.CheckState.Unchecked)
        else:
            self.ui.cb_select_all.setCheckState(Qt.CheckState.PartiallyChecked)
        self.ui.b_remove.setEnabled(count > 0)

    def _check_if_no_artists(self):
        if self.ui.listWidget.count() > 0:
            return

        QtWidgets.QMessageBox.warning(
            self,
            SharedVars.api.tr(self._NO_ARTISTS_TITLE),
            SharedVars.api.tr(self._NO_ARTISTS_TEXT),
            QtWidgets.QMessageBox.StandardButton.Ok,
            QtWidgets.QMessageBox.StandardButton.Ok,
        )
        self.close()


def initialize_cache_db() -> None:
    """Initialize the cache database for the plugin."""
    if os.path.exists(DB_FILE):
        DatabaseUtils.update_database_schema()
    else:
        SharedVars.api.logger.info("Creating new database file: %s", DB_FILE)
        DatabaseUtils.initialize_database()
        DatabaseUtils.update_database_schema()
        old_cache_file = os.path.join(DB_DIR, BASE_FILENAME + '.json')
        if os.path.exists(old_cache_file):
            SharedVars.api.logger.info("Importing cache file: %s", old_cache_file)
            DatabaseUtils.import_from_json(old_cache_file, save_artists=SharedVars.save_artists)
            try:
                os.remove(old_cache_file)
                SharedVars.api.logger.info("Removed old cache file: %s", old_cache_file)
            except OSError as e:
                SharedVars.api.logger.warning("Error removing old cache file: %s", e)

    ArtistDetailsPlugin.process_orphan_areas()


class BackgroundProcessingAction(BaseAction):
    TITLE = t_("ui.action.background_processing.title", "Start background area retrieval processing")

    def callback(self, objs):
        SharedVars.api.logger.debug("Background area retrieval processing started.")
        ArtistDetailsPlugin.process_orphan_areas()


def enable(api: PluginApi) -> None:
    """Called when the plugin is enabled.

    Args:
        api (PluginApi): The api for the plugin.
    """
    # Initialize settings
    api.plugin_config.register_option(OPT_PROCESS_TRACKS, False)
    api.plugin_config.register_option(OPT_AREA_COUNTY, True)
    api.plugin_config.register_option(OPT_AREA_MUNICIPALITY, True)
    api.plugin_config.register_option(OPT_AREA_SUBDIVISION, True)
    api.plugin_config.register_option(OPT_USE_CACHE, True)
    api.plugin_config.register_option(OPT_SAVE_ARTISTS_IN_CACHE, True)
    api.plugin_config.register_option(OPT_BACKGROUND_FETCH_AREAS, False)
    api.plugin_config.register_option(OPT_BACKGROUND_FETCH_INTERVAL, 60)

    # Migrate settings from 2.x version if available
    migrate_settings(api)

    SharedVars.api = api

    plugin = ArtistDetailsPlugin
    # plugin.api = api
    plugin.has_debug_if = hasattr(api.logger, 'debug_if')

    api.register_options_page(AdditionalArtistsDetailsOptionsPage)
    api.register_album_post_removal_processor(plugin.remove_album)

    # Register the plugin to run at a high priority.
    api.register_album_metadata_processor(plugin.make_album_vars, priority=100)
    api.register_track_metadata_processor(plugin.make_track_vars, priority=100)

    # Set shared variables for use within various classes and modules
    SharedVars.use_persistent_cache = api.plugin_config[OPT_USE_CACHE]
    SharedVars.save_artists = api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE]
    SharedVars.background_processing_enabled = api.plugin_config[OPT_BACKGROUND_FETCH_AREAS]
    SharedVars.background_processing_interval = api.plugin_config[OPT_BACKGROUND_FETCH_INTERVAL]
    SharedVars.background_processing_running = False

    if SharedVars.use_persistent_cache:
        initialize_cache_db()
    else:
        api.logger.info("Persistent cache is diabled.")

    # Register menu action to start background processing
    api.register_tools_menu_action(BackgroundProcessingAction)


def disable():
    """Called when plugin is disabled."""
    pass


def migrate_settings(api: PluginApi) -> None:
    """Migrate Picard 2.x settings if available.

    Args:
        api (PluginApi): The api for the plugin.
    """
    if api.global_config.setting.raw_value('aad_process_tracks') is None:
        return

    api.logger.info("Migrating settings from 2.x version.")

    mapping = [
        ('aad_process_tracks', OPT_PROCESS_TRACKS, bool),
        ('aad_area_county', OPT_AREA_COUNTY, bool),
        ('aad_area_municipality', OPT_AREA_MUNICIPALITY, bool),
        ('aad_area_subdivision', OPT_AREA_SUBDIVISION, bool),
    ]

    for old_key, new_key, qtype in mapping:
        if api.global_config.setting.raw_value(old_key) is None:
            api.logger.debug(
                "No old setting for key: '%s'",
                old_key,
            )
            continue
        api.plugin_config[new_key] = api.global_config.setting.raw_value(old_key, qtype=qtype)
        api.global_config.setting.remove(old_key)
