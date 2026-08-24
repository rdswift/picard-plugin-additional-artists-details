"""Additional Artists Details"""

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


from collections import namedtuple
from copy import deepcopy
from functools import partial
import json
import os
import threading
from typing import Callable

from PyQt6 import QtWidgets
from PyQt6.QtCore import (
    QStandardPaths,
    Qt,
)

from picard.debug_opts import DebugOpt
from picard.plugin3.api import (
    Album,
    Metadata,
    OptionsPage,
    PluginApi,
    Track,
    t_,
)
from picard.ui import PicardDialog
from picard.ui.util import FileDialog
from picard.util import open_local_path
from picard.webservice.api_helpers import MBAPIHelper

from .ui_artists_cache_editor import Ui_AdditionalArtistsDetailsCacheEditor
from .ui_options_additional_artists_details import Ui_AdditionalArtistsDetailsOptionsPage


USER_GUIDE_URL = 'https://picard-plugins-user-guides.readthedocs.io/en/latest/additional_artists_details/user_guide.html'

# Named tuple for code clarity
MetadataPair = namedtuple('MetadataPair', ['artists', 'target'])

# MusicBrainz ID codes for relationship types
RELATIONSHIP_TYPE_PART_OF = 'de7cc874-8b1b-3a05-8272-f3834c968fb7'

# MusicBrainz ID codes for area types
AREA_TYPE_COUNTRY = '06dd0ae4-8c74-30bb-b43d-95dcedf961de'
AREA_TYPE_COUNTY = 'bcecec27-8bdb-3e00-8254-d948dda502fa'
AREA_TYPE_MUNICIPALITY = '17246454-5ac4-36a1-b81a-4753eb2dab20'
AREA_TYPE_SUBDIVISION = 'fd3d44c5-80a1-3842-9745-2c4972d35afa'

CONDITIONAL_LOCATIONS = {AREA_TYPE_COUNTY, AREA_TYPE_MUNICIPALITY, AREA_TYPE_SUBDIVISION}

# Standard text for arguments
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

lock = threading.Lock()


class CustomHelper(MBAPIHelper):
    """Custom MusicBrainz API helper to retrieve artist and area information.
    """

    def get_artist_by_id(self, _id: str, handler: Callable, inc: list = None, priority: bool = False, important:bool = False,
                         mblogin: bool = False, refresh: bool = False):
        """Get information for the specified artist MBID.

        Args:
            _id (str): Artist MBID to retrieve.
            handler (Callable): Callback used to process the returned information.
            inc (list, optional): List of includes to add to the API call. Defaults to None.
            priority (bool, optional): Process the request at a high priority. Defaults to False.
            important (bool, optional): Identify the request as important. Defaults to False.
            mblogin (bool, optional): Request requires logging into MusicBrainz. Defaults to False.
            refresh (bool, optional): Request triggers a refresh. Defaults to False.

        Returns:
            PendingRequest: Requested task object.
        """
        return self._get_by_id(ARTIST, _id, handler, inc, priority=priority, important=important, mblogin=mblogin, refresh=refresh)

    def get_area_by_id(self, _id: str, handler: Callable, inc: list = None, priority: bool = False, important: bool = False,
                       mblogin: bool = False, refresh: bool = False):
        """Get information for the specified area MBID.

        Args:
            _id (str): Area MBID to retrieve.
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

        return self._get_by_id(AREA, _id, handler, inc, priority=priority, important=important, mblogin=mblogin, refresh=refresh)


class Area:
    """Class to hold information about an area id"""
    def __init__(self, parent: str, name: str, country: str, area_type: str, type_text: str):
        """Initialize an Area class object.

        Args:
            parent (str): MBID of the area's parent.
            name (str): Name of the area.
            country (str): Two-character country code if the area is a coountry, otherwise an empty string.
            area_type (str): MBID type code of the area.
            type_text (str): Text of the area's type.
        """
        self.parent = parent
        self.name = name
        self.country = country
        self.area_type = area_type
        self.type_text = type_text

    def as_dict(self) -> dict:
        """Return the instance as a dictionary.

        Returns:
            dict: Dictionary of the area information.
        """
        return {
            'parent': self.parent,
            'name': self.name,
            'country': self.country,
            'area_type': self.area_type,
            'type_text': self.type_text,
        }

    @classmethod
    def from_dict(cls, area_dict: dict) -> 'Area':
        """Create an Area object from a dictionary.

        Args:
            area_dict (dict): Dictionary of the area information.  Must include 'parent' (MBID of the area's parent),
            'name' (name of the area), 'country' (2-character country code), 'area_type' (the area's type code MBID),
            and 'type_text' (text of the area's type) elements.

        Returns:
            Area: The Area object based on the input dictionary.
        """
        return Area(
            parent=area_dict['parent'],
            name=area_dict['name'],
            country=area_dict['country'],
            area_type=area_dict['area_type'],
            type_text=area_dict['type_text'],
        )


class CacheException(Exception):
    """Custom exception for the cache"""


class DataCache:
    FILE_PROCESSING_EXCEPTION_MESSAGE = "Cache file processing already in progress."
    cache: dict = {
        'artist': {},
        'area': {},
    }
    is_dirty: bool = False
    _file_processing = False
    cache_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    cache_file = os.path.join(cache_dir, 'aad_cache.json')
    save_artists = True

    @classmethod
    def get_artist_cache(cls) -> dict:
        """Get the artist cache dictionary.

        Returns:
            dict: Artist information in the cache.
        """
        with lock:
            return cls.cache['artist']

    @classmethod
    def get_area_cache(cls) -> dict:
        """Get the area cache dictionary.

        Returns:
            dict: Area information in the cache.
        """
        with lock:
            return cls.cache['area']

    @classmethod
    def set_artist_info(cls, artist_id: str, artist_info: dict) -> None:
        """Set the artist information in the cache.

        Args:
            artist_id (str): MBID of the artist.
            artist_info (dict): Artist information to store.
        """
        with lock:
            cls.cache['artist'][artist_id] = artist_info
            cls.is_dirty = True

    @classmethod
    def remove_artist_info(cls, artist_id: str) -> None:
        """Remove the specified artist information from the cache.

        Args:
            artist_id (str): MBID of the artist.
        """
        with lock:
            if artist_id in cls.cache['artist']:
                del cls.cache['artist'][artist_id]
                cls.is_dirty = True

    @classmethod
    def get_artist_info(cls, artist_id: str) -> dict:
        """Get the dictionary of information for an artist.

        Args:
            artist_id (str): MBID of the artist.

        Returns:
            dict: Artist information. Empty dictionary if the artist is not in the cache.
        """
        with lock:
            return deepcopy(cls.cache['artist'][artist_id]) if artist_id in cls.cache['artist'] else {}

    @classmethod
    def set_area_info(cls, area_id: str, area_info: Area | dict) -> None:
        """Set the area information in the cache.

        Args:
            area_id (str): MBID of the area.
            area_info (Area | dict): Area information to store.
        """
        with lock:
            cls.cache['area'][area_id] = area_info.as_dict() if isinstance(area_info, Area) else area_info
            cls.is_dirty = True

    @classmethod
    def get_area_info(cls, area_id: str) -> Area:
        """Get the information for an area.

        Args:
            area_id (str): MBID of the area.

        Returns:
            Area: Area information. Empty Area object if the area is not in the cache.
        """
        if area_id not in cls.cache['area']:
            return Area('', '', '', '', '')
        with lock:
            return Area.from_dict(cls.cache['area'][area_id])

    @classmethod
    def _load_cache(cls, filename: str | None = None) -> None:
        with open(filename or cls.cache_file, 'r', encoding='utf8') as f:
            info_dict = json.load(fp=f)

        for key, value in info_dict['artist'].items():
            if key not in cls.cache['artist']:
                cls.set_artist_info(key, value)

        for key, value in info_dict['area'].items():
            if key not in cls.cache['area']:
                cls.set_area_info(key, value)

    @classmethod
    def _save_cache(cls, filename: str | None = None, save_artists: bool = True) -> None:
        cache = deepcopy(cls.cache)
        if not save_artists:
            cache['artist'] = {}
        with open(filename or cls.cache_file, 'w', encoding='utf8') as f:
            json.dump(cache, fp=f, indent=4, sort_keys=True)

    @classmethod
    def load_cache(cls) -> None:
        """Loads the cache from the persistent cache file.
        """
        if cls._file_processing:
            raise CacheException(cls.FILE_PROCESSING_EXCEPTION_MESSAGE)

        cls._file_processing = True
        try:
            cls._load_cache()
        except (KeyError, FileNotFoundError, OSError, json.JSONDecodeError) as ex:
            raise CacheException(f"Error loading cache: {ex}")
        finally:
            cls._file_processing = False

    @classmethod
    def save_cache(cls, save_artists: bool | None = None) -> None:
        """Save the cache to the persistent cache file.
        """
        error_prefix = "Error saving cache:"
        if not cls.is_dirty:
            raise CacheException("Cache has not changed.  Save canceled.")

        if cls._file_processing:
            raise CacheException(f"{error_prefix} {cls.FILE_PROCESSING_EXCEPTION_MESSAGE}")

        cls._file_processing = True

        artists_save = cls.save_artists if save_artists is None else save_artists
        try:
            cls._save_cache(save_artists=artists_save)
            cls.is_dirty = False
        except (OSError, TypeError, RecursionError, ValueError) as ex:
            raise CacheException(f"{error_prefix} {ex}")
        finally:
            cls._file_processing = False

    @classmethod
    def import_cache(cls, filename: str) -> None:
        """Import new items into the cache from the specified cache file. Save the cache to the
        persistent cache file if new information was added.

        Args:
            filename (str): Path and name of the cache file to import.
        """
        cls._load_cache(filename=filename)
        if cls.is_dirty:
            cls.save_cache()

    @classmethod
    def export_cache(cls, filename: str, save_artists: bool = True) -> None:
        """Export the current cache to the specified cache file.

        Args:
            filename (str): Path and name of the cache file to export.
        """
        cls._save_cache(filename=filename, save_artists=save_artists)


class ArtistDetailsPlugin:
    """Plugin to retrieve artist details, including area and country information.
    """

    # Area types to exclude from the location string
    EXCLUDE_AREA_TYPES = {AREA_TYPE_MUNICIPALITY, AREA_TYPE_COUNTY, AREA_TYPE_SUBDIVISION}

    cache_requests = {
        'artist': set(),
        'area': set(),
    }
    album_processing_count = {}
    albums = {}
    album_area_requests: dict[str, set] = {}

    def __init__(self, api: PluginApi) -> None:
        self.api = api
        self.has_debug_if = hasattr(api.logger, 'debug_if')

    def _debug_logger(self, text: str) -> None:
        """Debug logging helper to use `debug_if()` if available.

        Args:
            text (str): Message to log.
        """
        if self.has_debug_if:
            self.api.logger.debug_if(DebugOpt.PLUGIN_DEVELOPMENT, text)
        else:
            self.api.logger.debug(text)

    def _add_album_area_request(self, album_id: str, area_id: str) -> None:
        if album_id not in self.album_area_requests:
            self.album_area_requests[album_id] = set()
        self.album_area_requests[album_id].add(area_id)

    def _remove_album_area_request(self, album_id: str, area_id: str) -> None:
        if album_id in self.album_area_requests:
            self.album_area_requests[album_id].discard(area_id)

    def _get_album_area_request_count(self, album_id: str) -> int:
        if album_id not in self.album_area_requests:
            return 0
        return len(self.album_area_requests[album_id])

    def _make_empty_target(self, album_id: str) -> None:
        """Create an empty album target node if it doesn't exist.

        Args:
            album_id (str): MBID of the album.
        """
        if album_id not in self.albums:
            self.albums[album_id] = {ALBUM_ARTISTS: set(), TRACKS: []}

    def _add_target(self, album_id: str, artists: set, target_metadata: Metadata) -> None:
        """Add a metadata target to update for an album.

        Args:
            album_id (str): MBID of the album.
            artists (set): Set of artists to include.
            target_metadata (Metadata): Target metadata to update.
        """
        self._make_empty_target(album_id)
        self.albums[album_id][TRACKS].append(MetadataPair(artists, target_metadata))

    def _remove_album(self, album_id: str) -> None:
        """Removes an album from the metadata processing dictionary.

        Args:
            album_id (str): MBID of the album to remove.
        """
        self._debug_logger(f"Removing album '{album_id}'")
        self.albums.pop(album_id, None)
        self.album_processing_count.pop(album_id, None)

    def _album_add_request(self, album: Album) -> None:
        """Increment the number of pending requests for an album.

        Args:
            album (Album): The Album object to use for the processing.
        """
        if album.id not in self.album_processing_count:
            self.album_processing_count[album.id] = 0
        self.album_processing_count[album.id] += 1

    def _album_remove_request(self, album: Album) -> None:
        """Decrement the number of pending requests for an album.  Trigger
        album finalization if there are no outstanding requests.

        Args:
            album (api.Album): The Album object to use for the processing.
        """
        if album.id not in self.album_processing_count:
            self.album_processing_count[album.id] = 1
        self.album_processing_count[album.id] -= 1

        if self.album_processing_count[album.id]:
            return

        self._debug_logger(f"Finalizing loading of album: {album}")
        if self._save_artist_metadata(album):
            album._finalize_loading(None)

        # Save the cache to a file
        try:
            DataCache.save_cache()
        except CacheException as ex:
            self.api.logger.error(str(ex))

    def remove_album(self, _api: PluginApi, album: Album) -> None:
        """Remove the album from the albums processing dictionary.

        Args:
            _api (PluginApi): The plugin API object.
            album (Album): The album object to remove.
        """
        self._remove_album(album.id)

    def make_album_vars(self, _api: PluginApi, album: Album, album_metadata, _release_node: dict) -> None:
        """Process album artists.

        Args:
            _api (PluginApi): The plugin API object.
            album (Album): The Album object to use for the processing.
            album_metadata (Metadata): Metadata object for the album.
            _release_metadata (dict): Dictionary of release data from MusicBrainz api.
        """
        self._debug_logger(f"Processing album: {album.id}")
        artists = set(artist.id for artist in album.get_album_artists())
        self._make_empty_target(album.id)
        self.albums[album.id][ALBUM_ARTISTS] = artists

        if not self.api.plugin_config[OPT_PROCESS_TRACKS]:
            self.api.logger.info("Track artist processing is disabled.")

        self._artist_processing(artists, album, album_metadata, 'Album')

    def _set_track_with_no_artists(self, track: Track, track_metadata: Metadata) -> None:
        album = track.album
        # self._save_artist_metadata(album)
        for artist in self.albums[album.id][ALBUM_ARTISTS]:
            # self._set_artist_metadata(track_metadata, artist, self.result_cache[ARTIST][artist])
            self._set_artist_metadata(track_metadata, artist)
        return

    def make_track_vars(self, _api: PluginApi, track: Track, track_metadata: Metadata,
                        track_node: dict, _release_node: dict) -> None:
        """Process track artists.

        Args:
            _api (PluginApi): The plugin API object.
            track (Track): The Track object to use for the processing.
            track_metadata (Metadata): Metadata object for the album.
            track_node (dict): Dictionary of track data from MusicBrainz api.
            _release_node (dict): Dictionary of release data from MusicBrainz api.
        """
        if not self.api.plugin_config[OPT_PROCESS_TRACKS]:
            self._set_track_with_no_artists(track, track_metadata)
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
                    self._metadata_error(album.id, 'artist-credit.artist', source_type)
        else:
            # No valid metadata found.  Log as error.
            self._metadata_error(album.id, 'artist-credit', source_type)

        if not artists:
            self._set_track_with_no_artists(track, track_metadata)
            return

        self._artist_processing(artists, album, track_metadata, 'Track')

    def _artist_processing(self, artists: set, album: Album, destination_metadata: Metadata, source_type: str) -> None:
        """Retrieves the information for each artist not already processed.

        Args:
            artists (set): Set of artist MBIDs to process.
            album (Album): Album object to use for the processing.
            destination_metadata (Metadata): Metadata object to update with the new variables.
            source_type (str): Source type (album or track) for logging messages.
        """
        for temp_id in artists:
            # if temp_id not in self.result_cache[ARTIST_REQUESTS]:
            if temp_id not in self.cache_requests['artist'] and temp_id not in DataCache.cache['artist']:
                # self.result_cache[ARTIST_REQUESTS].add(temp_id)
                self.cache_requests['artist'].add(temp_id)
                self.api.logger.debug('Retrieving artist ID %s information from MusicBrainz.', temp_id)
                self._get_artist_info(temp_id, album)
            else:
                self._debug_logger(f"{source_type} artist ID {temp_id} information available from cache.")

        self._add_target(album.id, artists, destination_metadata)
        self._save_artist_metadata(album)

    def _save_artist_metadata(self, album: Album) -> bool:
        """Saves the new artist details variables to the metadata targets for the specified album.

        Args:
            album (Album): The album to process.
        """
        album_id = album.id

        if album_id in self.album_processing_count and self.album_processing_count[album_id]:
            return False

        if self._get_album_area_request_count(album_id):
            return False

        if album_id not in self.albums or not self.albums[album_id][TRACKS]:
            self.api.logger.error("No metadata targets found for album '%s'", album_id)
            return False

        for item in self.albums[album_id][TRACKS]:
            # Add album artists to track so they are available in the metadata
            artists = self.albums[album_id][ALBUM_ARTISTS].copy().union(item.artists)
            destination_metadata = item.target
            for artist in artists:
                # if artist in self.result_cache[ARTIST]:
                if artist in self.cache_requests['artist'] or artist in DataCache.cache['artist']:
                    # self._set_artist_metadata(destination_metadata, artist, self.result_cache[ARTIST][artist])
                    self._set_artist_metadata(destination_metadata, artist)

        return True

    # def _set_artist_metadata(self, destination_metadata: Metadata, artist_id: str, artist_info: dict) -> None:
    def _set_artist_metadata(self, destination_metadata: Metadata, artist_id: str) -> None:
        """Adds the artist information to the destination metadata.

        Args:
            destination_metadata (Metadata): Metadata object to update with new variables.
            artist_id (str): MBID of the artist to update.
            artist_info (dict): Dictionary of information for the artist.
        """
        def _set_item(key, value):
            destination_metadata[f"~artist_{artist_id}_{key.replace('-', '_')}"] = value

        artist_info = DataCache.get_artist_info(artist_id)

        for item in artist_info.keys():
            if item in {'area', 'begin-area', 'end-area'}:
                country, location = self._drill_area(artist_info[item])
                if country:
                    _set_item(item.replace('area', 'country'), country)
                if location:
                    _set_item(item.replace('area', 'location'), location)
            else:
                _set_item(item, artist_info[item])

    def _get_artist_info(self, artist_id: str, album: Album) -> None:
        """Gets the artist information from the MusicBrainz website.

        Args:
            artist_id (str): MBID of the artist to retrieve.
            album (Album): The Album object to use for the processing.
        """
        self._album_add_request(album)
        task_id = f"Artist={artist_id}"
        helper = CustomHelper(album.tagger.webservice)
        handler = partial(
            self._artist_submission_handler,
            artist=artist_id,
            album=album,
            task_id=task_id,
        )

        return self.api.add_album_task(
            album=album,
            task_id=task_id,
            description=f"Get info for artist: {artist_id}",
            timeout=10.,
            request_factory=lambda: helper.get_artist_by_id(artist_id, handler),
            blocking=True,
        )

    def _artist_submission_handler(self, document, _reply, error, artist=None, album=None, task_id=None) -> None:
        """Handles the response from the webservice requests for artist information.
        """
        try:
            if error:
                self.api.logger.error("Artist '%s' information retrieval error.", artist)
                return

            artist_info = {}
            for item in ['type', 'gender', 'name', 'sort-name', 'disambiguation']:
                if item in document and document[item]:
                    artist_info[item] = document[item]

            if 'life-span' in document:
                for item in ['begin', 'end']:
                    if item in document['life-span'] and document['life-span'][item]:
                        artist_info[item] = document['life-span'][item]

            for item in ['area', 'begin-area', 'end-area']:
                if item in document and document[item] and 'id' in document[item] and document[item]['id']:
                    area_id = document[item]['id']
                    artist_info[item] = area_id
                    # if area_id not in self.result_cache[AREA_REQUESTS]:
                    if area_id not in self.cache_requests['area'] and area_id not in DataCache.cache['area']:
                        self._get_area_info(area_id, album)

            DataCache.set_artist_info(artist_id=artist, artist_info=artist_info)

        finally:
            self.api.complete_album_task(album=album, task_id=task_id)
            self._album_remove_request(album)

    def _get_area_info(self, area_id: str, album: Album) -> None:
        """Gets the area information from the MusicBrainz website.

        Args:
            area_id (str): MBID of the area to retrieve.
            album (Album): The Album object to use for the processing.
        """
        task_id = f"Area={area_id}"
        self.cache_requests['area'].add(area_id)
        self._album_add_request(album)
        self._add_album_area_request(album.id, area_id)
        self.api.logger.debug('Retrieving area ID %s from MusicBrainz.', area_id)
        helper = CustomHelper(album.tagger.webservice)
        handler = partial(
            self._area_submission_handler,
            area=area_id,
            album=album,
            task_id=task_id,
        )

        return self.api.add_album_task(
            album=album,
            task_id=task_id,
            description=f"Get info for area: {area_id}",
            timeout=10.,
            request_factory=lambda: helper.get_area_by_id(area_id, handler),
            blocking=True,
        )

    def _area_submission_handler(self, document, _reply, error, area=None, album=None, task_id=None) -> None:
        """Handles the response from the webservice requests for area information.
        """
        try:
            if error:
                self.api.logger.error("Area '%s' information retrieval error.", area)
                return

            area_info = self._parse_area(document)
            new_id = area_info.parent

            if area_info.area_type == AREA_TYPE_COUNTRY and new_id not in DataCache.cache['area']:
                self._area_logger(
                    area_id=new_id,
                    area_name=f"{area_info.name} ({area_info.country})",
                    area_type=area_info.type_text,
                )
                area_info.parent = ''
                DataCache.set_area_info(area_id=new_id, area_info=area_info)

            if 'relations' in document:
                for rel in document['relations']:
                    self._parse_area_relation(
                        area_id=new_id,
                        area_relation=rel,
                        album=album,
                        area_name=area_info.name,
                        area_type=area_info.area_type,
                        area_type_text=area_info.type_text,
                    )

        finally:
            self.api.complete_album_task(album=album, task_id=task_id)
            self._remove_album_area_request(album.id, area)
            self._album_remove_request(album)

    def _area_logger(self, area_id: str, area_name: str, area_type: str) -> None:
        """Adds a log entry for the area retrieved.

        Args:
            area_id (str): MBID of the area added.
            area_name (str): Name of the area added.
            area_type (str): Type of area added.
        """
        self._debug_logger(f"Adding area: {area_id} => \"{area_name}\" of type '{area_type}'")

    def _parse_area_relation(self, area_id: str, area_relation: dict, album: Album, area_name: str,
                             area_type: str, area_type_text: str) -> None:
        """Parse an area relation to extract the area information.

        Args:
            area_id (str): MBID of the area providing the relationship.
            area_relation (dict): Dictionary of the area relationship.
            album (Album): The Album object to use for the processing.
            area_name (str): Name of the area providing the relationship.
            area_type (str): MBID of the type of area providing the relationship.
            area_type_text (str): Text description of the area providing the relationship.
        """
        if 'type-id' not in area_relation or 'area' not in area_relation or area_relation['type-id'] != RELATIONSHIP_TYPE_PART_OF:
            return

        area_info = self._parse_area(area_relation['area'])

        if not area_info.parent:
            return

        def _add_country(_id, name, country, _type, type_text):
            # if _id not in self.result_cache[AREA]:
            if _id not in DataCache.get_area_cache():
                self._area_logger(_id, f"{name} ({country})", type_text)
                # self.result_cache[AREA][_id] = Area('', name, country, _type, type_text)
                DataCache.set_area_info(_id, Area('', name, country, _type, type_text))
                self.cache_requests['area'].add(_id)

        if 'direction' in area_relation and area_relation['direction'] == 'backward':
            if area_id not in self.cache_requests['area']:
                self._area_logger(area_id, area_name, area_type_text)
                DataCache.set_area_info(
                    area_id=area_id,
                    area_info=Area(
                        parent=area_info.parent,
                        name=area_name,
                        country='',
                        area_type=area_type,
                        type_text=area_type_text,
                    )
                )
                self.cache_requests['area'].add(area_id)

            if area_info.area_type == AREA_TYPE_COUNTRY:
                _add_country(
                    _id=area_info.parent,
                    name=area_info.name,
                    country=area_info.country,
                    _type=area_info.area_type,
                    type_text=area_info.type_text,
                )

            else:
                if area_info.parent not in DataCache.cache['area'] and area_info.parent not in self.cache_requests['area']:
                    self._get_area_info(area_info.parent, album)

        elif 'direction' in area_relation and area_relation['direction'] == 'forward' and area_info.area_type == AREA_TYPE_COUNTRY:
            _add_country(
                _id=area_info.parent,
                name=area_info.name,
                country=area_info.country,
                _type=area_info.area_type,
                type_text=area_info.type_text,
            )

        else:
            self._area_logger(
                area_id=area_info.parent,
                area_name=area_info.name,
                area_type=area_info.type_text,
            )
            self.cache_requests['area'].add(area_info.parent)
            _id = area_info.parent
            area_info.parent = area_id
            area_info.country = ''
            DataCache.set_area_info(_id, area_info)

    @staticmethod
    def _parse_area(area_info: dict) -> Area:
        """Parse a dictionary of area information to return selected elements.

        Args:
            area_info (dict): Area information to parse.

        Returns:
            tuple: Selected information for the area (id, name, country code, type code, type text).
        """
        if 'id' not in area_info:
            return Area('', '', '', '', '')

        area_id = area_info['id']
        area_name = area_info['name'] if 'name' in area_info else 'Unknown Name'
        area_type = area_info['type-id'] if 'type-id' in area_info else ''
        area_type_text = area_info['type'] if 'type' in area_info else 'Unknown Area Type'
        country = ''

        if area_type == AREA_TYPE_COUNTRY:
            if ISO_CODES_1 in area_info and area_info[ISO_CODES_1]:
                country = area_info[ISO_CODES_1][0]
            elif ISO_CODES_2 in area_info and area_info[ISO_CODES_2]:
                country = area_info[ISO_CODES_2][0][:2]

        return Area(area_id, area_name, country, area_type, area_type_text)

    def _metadata_error(self, album_id: str, metadata_element: str, metadata_group: str) -> None:
        """Logs metadata-related errors.

        Args:
            album_id (str): MBID of the album being processed.
            metadata_element (str): Metadata element initiating the error.
            metadata_group (str): Metadata group initiating the error.
        """
        self.api.logger.error("Album '%s' missing '%s' in %s metadata.", album_id, metadata_element, metadata_group)

    def _drill_area(self, area_id: str) -> tuple[str, str]:
        """Drills up from the specified area to determine the two-character
        country code and the full location description for the area.

        Args:
            area_id (str): MBID of the area to process.

        Returns:
            tuple: The two-character country code and full location description for the area.
        """
        country = ''
        location = []
        i = 7   # Counter to avoid potential runaway processing

        while i and area_id and not country:
            i -= 1
            area = DataCache.get_area_info(area_id)
            country = area.country
            area_id = area.parent

            if not location or area.area_type not in CONDITIONAL_LOCATIONS:
                location.append(area.name)
            else:
                if (
                    (area.area_type == AREA_TYPE_COUNTY and self.api.plugin_config[OPT_AREA_COUNTY])
                    or (area.type == AREA_TYPE_MUNICIPALITY and self.api.plugin_config[OPT_AREA_MUNICIPALITY])
                    or (area.type == AREA_TYPE_SUBDIVISION and self.api.plugin_config[OPT_AREA_SUBDIVISION])
                ):
                    location.append(area.name)

        return country, ', '.join(location)


class AdditionalArtistsDetailsOptionsPage(OptionsPage):
    """Options page for the Additional Artists Details plugin.
    """

    TITLE = t_("ui.title", "Additional Artists Details")
    HELP_URL = USER_GUIDE_URL

    _ERR_MSG_TITLE = t_('ui.error.cache_title', "Cache Error")
    _ERR_MSG_CACHE_LOAD = t_('ui.error.cache_load', "Error loading the cache file.\n\n%s")
    _ERR_MSG_CACHE_SAVE = t_('ui.error.cache_save', "Error saving the cache file.\n\n%s")
    _ERR_MSG_CACHE_IMPORT = t_('ui.error.cache_import', "Error importing the cache file.\nFile: %s\n\n%s")
    _ERR_MSG_CACHE_EXPORT = t_('ui.error.cache_export', "Error exporting the cache file.\nFile: %s\n\n%s")
    _SUCCESS_LOAD = t_('ui.success.load', "Successfully reloaded the cache file.")
    _SUCCESS_SAVE = t_('ui.success.save', "Successfully updated the cache file.")
    _SUCCESS_IMPORT = t_('ui.success.import', "Successfully imported the cache file.\nFile: %s")
    _SUCCESS_EXPORT = t_('ui.success.export', "Successfully exported the cache file.\nFile: %s")
    _FILTER_ALL = t_('ui.filter.all', "All files")
    _FILTER_JSON = t_('ui.filter.json', "JSON files")

    def __init__(self, parent=None) -> None:
        super(AdditionalArtistsDetailsOptionsPage, self).__init__(parent)

        self.ui = Ui_AdditionalArtistsDetailsOptionsPage()
        self.ui.setupUi(self)

        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_DirOpenIcon)
        self.ui.b_open_cache_directory.setIcon(icon)

        self.ui.b_open_cache_directory.clicked.connect(self.open_cache_directory)
        self.ui.b_edit_cache.clicked.connect(self.cache_edit)
        self.ui.b_load_cache.clicked.connect(self.cache_load)
        self.ui.b_save_cache.clicked.connect(self.cache_save)
        self.ui.b_import_cache.clicked.connect(self.cache_import)
        self.ui.b_export_cache.clicked.connect(self.cache_export)

        self.save_artists_changed = False
        self.ui.cb_save_artists.stateChanged.connect(self._save_artists_state_changed)

        self.ui.cache_file.setText(DataCache.cache_file)

        self.api = PluginApi.get_api()

        self.filter_all = self.api.tr(self._FILTER_ALL) + " (*)"
        self.filter_json = self.api.tr(self._FILTER_JSON) + " (*.json)"

        self.user_documents_dir = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.DocumentsLocation)

    def load(self) -> None:
        """Load the option settings.
        """
        self.ui.cb_process_tracks.setChecked(self.api.plugin_config[OPT_PROCESS_TRACKS])
        self.ui.cb_area_county.setChecked(self.api.plugin_config[OPT_AREA_COUNTY])
        self.ui.cb_area_municipality.setChecked(self.api.plugin_config[OPT_AREA_MUNICIPALITY])
        self.ui.cb_area_subdivision.setChecked(self.api.plugin_config[OPT_AREA_SUBDIVISION])
        self.save_artists = self.api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE]
        self.ui.cb_save_artists.setChecked(self.save_artists)
        self._set_edit_button_state()

    def save(self) -> None:
        """Save the option settings.
        """
        self.api.plugin_config[OPT_PROCESS_TRACKS] = self.ui.cb_process_tracks.isChecked()
        self.api.plugin_config[OPT_AREA_COUNTY] = self.ui.cb_area_county.isChecked()
        self.api.plugin_config[OPT_AREA_MUNICIPALITY] = self.ui.cb_area_municipality.isChecked()
        self.api.plugin_config[OPT_AREA_SUBDIVISION] = self.ui.cb_area_subdivision.isChecked()
        DataCache.save_artists = self.ui.cb_save_artists.isChecked()
        self.api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE] = DataCache.save_artists
        if DataCache.save_artists != self.save_artists:
            DataCache.is_dirty = True
        self.save_artists = DataCache.save_artists

    def _save_artists_state_changed(self) -> None:
        self.save_artists_changed = True
        self._set_edit_button_state()

    def _set_edit_button_state(self) -> None:
        self.ui.b_edit_cache.setEnabled(self.ui.cb_save_artists.isChecked())

    def cache_load(self) -> None:
        """Load the cache file.
        """
        try:
            DataCache.load_cache()
            QtWidgets.QMessageBox.information(
                self,
                None,
                self.api.tr(self._SUCCESS_LOAD),
            )
        except CacheException as ex:
            self.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                self.api.tr(self._ERR_MSG_TITLE),
                self.api.tr(self._ERR_MSG_CACHE_LOAD) % (ex,),
            )

    def cache_save(self) -> None:
        """Save the cache file.
        """
        if self.save_artists_changed:
            DataCache.is_dirty = True
            self.save_artists_changed = False

        save_artists = self.ui.cb_save_artists.isChecked()
        if save_artists != DataCache.save_artists:
            DataCache.is_dirty = True

        try:
            DataCache.save_cache(save_artists=save_artists)
            QtWidgets.QMessageBox.information(
                self,
                None,
                self.api.tr(self._SUCCESS_SAVE),
            )
        except CacheException as ex:
            self.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                self.api.tr(self._ERR_MSG_TITLE),
                self.api.tr(self._ERR_MSG_CACHE_SAVE) % (ex,),
            )

    def cache_import(self) -> None:
        """Import from a cache file.
        """
        filepath, _filter = FileDialog.getOpenFileName(
            parent=self,
            directory=self.user_documents_dir,
            filter=self.filter_json + ";;" + self.filter_all,
            initialFilter=self.filter_json,
        )
        if not filepath:
            return

        try:
            DataCache.import_cache(filename=filepath)
            QtWidgets.QMessageBox.information(
                self,
                None,
                self.api.tr(self._SUCCESS_IMPORT) % (filepath,)
            )
        except CacheException as ex:
            self.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                self.api.tr(self._ERR_MSG_TITLE),
                self.api.tr(self._ERR_MSG_CACHE_SAVE) % (filepath, ex,),
            )

    def cache_export(self) -> None:
        """Export to a cache file.
        """
        filepath, _filter = FileDialog.getSaveFileName(
            parent=self,
            directory=os.path.join(self.user_documents_dir, 'additional_artists_details_cache.json'),
            filter=self.filter_json + ";;" + self.filter_all,
            initialFilter=self.filter_json,
        )
        if not filepath:
            return

        save_artists = self.ui.cb_save_artists.isChecked()
        try:
            DataCache.export_cache(filename=filepath, save_artists=save_artists)
            QtWidgets.QMessageBox.information(
                self,
                None,
                self.api.tr(self._SUCCESS_EXPORT) % (filepath,)
            )
        except CacheException as ex:
            self.api.logger.error(str(ex))
            QtWidgets.QMessageBox.critical(
                self,
                self.api.tr(self._ERR_MSG_TITLE),
                self.api.tr(self._ERR_MSG_CACHE_SAVE) % (filepath, ex,),
            )

    def cache_edit(self) -> None:
        """Edit the cache and file.
        """
        editor = CacheEditorPage(self)
        editor.exec()

    def open_cache_directory(self) -> None:
        cache_dir = DataCache.cache_dir
        open_local_path(cache_dir)


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
        text=(
            "Artist removal from the cache successfully completed.\n\n"
            "Please save or export the cache to save the changes."
        ),
    )
    _FILTER_STATUS_UNFILTERED = t_('ui.filter_status.unfiltered', "(unfiltered)")
    _FILTER_STATUS_FILTERED = t_(
        key='ui.filter_status.filtered',
        text="({n} item)",
        plural="({n} items)",
    )

    def __init__(self, parent=None) -> None:
        super().__init__(parent)

        self.ui = Ui_AdditionalArtistsDetailsCacheEditor()
        self.ui.setupUi(self)

        self.matched_items = []

        icon_up = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowUp)
        icon_dn = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_ArrowDown)
        self.ui.b_filter_previous.setIcon(icon_up)
        self.ui.b_filter_next.setIcon(icon_dn)

        self.api = PluginApi.get_api()

        self.load_artists()
        self.update_checked_selector_state()

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

    def load_artists(self):
        self.ui.listWidget.clear()
        artists: dict = deepcopy(DataCache.cache['artist'])
        for artist_id, artist in sorted(artists.items(), key=lambda x: x[1]['sort-name']):
            item = QtWidgets.QListWidgetItem(f"{artist['sort-name']} [{artist['type']}]")
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
            item.setData(Qt.ItemDataRole.UserRole, artist_id)
            self.ui.listWidget.addItem(item)
        self.current_item = self.ui.listWidget.item(0)
        self.font_normal = self.current_item.font()
        self.font_bold = self.current_item.font()
        self.font_bold.setBold(True)

    def _update_filter_status(self):
        if self.ui.filter_text.text():
            self.ui.filter_status_label.setText(self.api.trn(*self._FILTER_STATUS_FILTERED, n=len(self.matched_items)))
        else:
            self.ui.filter_status_label.setText(self.api.tr(self._FILTER_STATUS_UNFILTERED))

    def filter_changed(self):
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

    def move_up(self):
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

    def move_down(self):
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

    def _move_current_item(self, item: QtWidgets.QListWidgetItem):
        self.ui.listWidget.setCurrentItem(item)
        self._set_up_down_states()

    def _set_up_down_states(self):
        if not self.matched_items:
            self.ui.b_filter_previous.setEnabled(False)
            self.ui.b_filter_next.setEnabled(False)
        else:
            # current_index = self.matched_items.index(self.current_item)
            current_index = self.ui.listWidget.currentRow()
            first_index = self.ui.listWidget.row(self.matched_items[0])
            last_index = self.ui.listWidget.row(self.matched_items[-1])
            self.ui.b_filter_previous.setEnabled(current_index > first_index)
            self.ui.b_filter_next.setEnabled(current_index < last_index)

    def list_item_changed(self, _item: QtWidgets.QListWidgetItem) -> None:
        self.update_checked_selector_state()

    def remove_artists(self) -> None:
        count = self.get_checked_count()
        if count < 1:
            return

        if QtWidgets.QMessageBox.warning(
            self,
            self.api.tr(self._CONFIRMATION_MSG_TITLE),
            self.api.trn(*self._CONFIRMATION_MSG_TEXT, n=count),
            QtWidgets.QMessageBox.StandardButton.Ok | QtWidgets.QMessageBox.StandardButton.Cancel,
            QtWidgets.QMessageBox.StandardButton.Cancel,
        ) == QtWidgets.QMessageBox.StandardButton.Cancel:
            return

        for index in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(index)
            if item.checkState() == Qt.CheckState.Checked:
                DataCache.remove_artist_info(item.data(Qt.ItemDataRole.UserRole))

        QtWidgets.QMessageBox.information(
            self,
            self.api.tr(self._SUCCESS_MSG_TITLE),
            self.api.tr(self._SUCCESS_MSG_TEXT),
        )

        self.close()

    def get_checked_count(self) -> int:
        count = 0
        for index in range(self.ui.listWidget.count()):
            if self.ui.listWidget.item(index).checkState() == Qt.CheckState.Checked:
                count += 1
        return count

    def selector_clicked(self):
        total = self.ui.listWidget.count()
        count = self.get_checked_count()
        set_state = Qt.CheckState.Checked if count < total else Qt.CheckState.Unchecked
        # for item in self.ui.listWidget.items():
        #     item: QtWidgets.QListWidgetItem
        for index in range(self.ui.listWidget.count()):
            item = self.ui.listWidget.item(index)
            item.setCheckState(set_state)
        count = total if set_state == Qt.CheckState.Checked else 0
        self.ui.checked_count_label.setText(f"({count:,}/{total:,})")
        self.ui.cb_select_all.setCheckState(set_state)
        self.ui.b_remove.setEnabled(count > 0)

    def update_checked_selector_state(self) -> None:
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


def enable(api: PluginApi) -> None:
    """Called when plugin is enabled."""
    # Initialize settings
    api.plugin_config.register_option(OPT_PROCESS_TRACKS, False)
    api.plugin_config.register_option(OPT_AREA_COUNTY, True)
    api.plugin_config.register_option(OPT_AREA_MUNICIPALITY, True)
    api.plugin_config.register_option(OPT_AREA_SUBDIVISION, True)
    api.plugin_config.register_option(OPT_SAVE_ARTISTS_IN_CACHE, True)

    # Migrate settings from 2.x version if available
    migrate_settings(api)

    plugin = ArtistDetailsPlugin(api)
    api.register_options_page(AdditionalArtistsDetailsOptionsPage)
    api.register_album_post_removal_processor(plugin.remove_album)

    # Register the plugin to run at a high priority.
    api.register_album_metadata_processor(plugin.make_album_vars, priority=100)
    api.register_track_metadata_processor(plugin.make_track_vars, priority=100)

    DataCache.save_artists = api.plugin_config[OPT_SAVE_ARTISTS_IN_CACHE]

    # Populate cache from file
    try:
        DataCache.load_cache()
    except CacheException as ex:
        api.logger.error(str(ex))


def disable():
    api = PluginApi.get_api()
    # Save the cache to a file
    try:
        DataCache.save_cache()
    except CacheException as ex:
        api.logger.error(str(ex))


def migrate_settings(api: PluginApi) -> None:
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
            api.logger.debug("No old setting for key: '%s'", old_key,)
            continue
        api.plugin_config[new_key] = api.global_config.setting.raw_value(old_key, qtype=qtype)
        api.global_config.setting.remove(old_key)
