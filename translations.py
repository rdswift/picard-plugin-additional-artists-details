"""Database utility functions for the Additional Artists Details plugin."""

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

from picard.plugin3.api import t_


class TxStrings:
    """Strings defined for translation"""

    # Options Page
    OPTIONS_PAGE_TITLE = t_("ui.title", "Additional Artists Details")
    DELETE_CONFIRMATION_MSG_TITLE = t_('ui.delete.confirmation.title', "Confirm Database Deletion")
    DELETE_CONFIRMATION_MSG_TEXT = t_(
        key='ui.delete.confirmation.message',
        text=(
            "You are about to delete the local persistent cache database file from your system. "
            "There is no way to undo this action.  Continue?"
        ),
    )
    DELETE_SUCCESS_TEXT = t_(
        key='ui.delete.success.message',
        text="The persistent cache database file has been successfully deleted.",
    )
    DELETE_RESULT_TITLE = t_('ui.delete.result.title', "Delete Database")
    DELETE_ERROR_TEXT = t_(
        key='ui.delete.error.message',
        text="There was a problem deleting the persistent cache database file.\n\nError: %s",
    )
    ERR_MSG_TITLE = t_('ui.error.cache_title', "Cache Error")
    ERR_MSG_CACHE_IMPORT = t_('ui.error.cache_import', "Error importing the cache file.\nFile: %s\n\n%s")
    ERR_MSG_CACHE_EXPORT = t_('ui.error.cache_export', "Error exporting the cache file.\nFile: %s\n\n%s")
    SUCCESS_IMPORT = t_('ui.success.import', "Successfully imported the cache file.\nFile: %s")
    SUCCESS_EXPORT = t_('ui.success.export', "Successfully exported the cache file.\nFile: %s")

    # File Filters
    FILTER_ALL = t_('ui.filter.all', "All files")
    FILTER_CSV = t_('ui.filter.csv', "CSV files")
    FILTER_DB = t_('ui.filter.db', "Database files")
    FILTER_JSON = t_('ui.filter.json', "JSON files")

    # Cache Status Page
    CACHE_MISSING_TEXT = t_(
        key='ui.notes.not_found.message',
        text="The cache database was not found.",
    )
    DATABASE_CACHE_DISABLED = t_(
        key='ui.notes.database_cache_disabled',
        text="The cache database is currently disabled. The in-memory session cache is being used.",
    )
    SESSION_CACHE_DISABLED = t_(
        key='ui.notes.session_cache_disabled',
        text="The in-memory session cache is currently disabled because the cache database is being used.",
    )
    ORPHANS_MSG_TEXT = t_(
        key='ui.notes.orphans.message', text="There are orphan area records. Missing parents: %s, Orphan areas: %s"
    )
    NO_ORPHANS_MSG_TEXT = t_(key='ui.notes.no_orphans.message', text="There are no orphan area records.")
    BACKGROUND_DISABLED_MSG_TEXT = t_(
        key='ui.notes.background_disabled.message', text="Background processing is currently disabled."
    )
    BACKGROUND_RUNNING_MSG_TEXT = t_(
        key='ui.notes.background_running.message', text="Background processing is enabled and currently running."
    )

    # Cache Editor Page
    CONFIRMATION_MSG_TITLE = t_('ui.remove.confirmation.title', "Confirm Removal")
    CONFIRMATION_MSG_TEXT = t_(
        key='ui.remove.confirmation.message',
        text="You are about to remove {n} artist record from the cache.  Continue?",
        plural="You are about to remove {n} artist records from the cache.  Continue?",
    )
    SUCCESS_MSG_TITLE = t_('ui.remove.success.title', "Artist Removal Success")
    SUCCESS_MSG_TEXT = t_(
        key='ui.remove.success.message',
        text="Artist removal from the cache successfully completed.",
    )
    FILTER_STATUS_UNFILTERED = t_('ui.filter_status.unfiltered', "(unfiltered)")
    FILTER_STATUS_FILTERED = t_(
        key='ui.filter_status.filtered',
        text="({n} item)",
        plural="({n} items)",
    )
    NO_ARTISTS_TITLE = t_('ui.no_artists.title', "No Artists")
    NO_ARTISTS_TEXT = t_(
        key='ui.no_artists.message',
        text="There were no artists found in the cache.  The editor will now close.",
    )

    # Actions
    MENU = (t_("ui.action.sub_menu.title", "Additional Artists Details"),)
    COMPACT_DATABASE = t_("ui.action.compact_database.title", "Compact the database")
    COMPACT_DATABASE_OKAY = t_(
        "ui.action.compact_database_okay.text",
        "The database file was compacted successfully.\n\nFile size reduction:",
    )
    COMPACT_DATABASE_ERROR = t_(
        "ui.action.compact_database_error.text",
        "There was an error while compacting the database file.  Please see the log for details.",
    )
    DISPLAY_STATUS = t_("ui.action.display_cache_status.title", "Display the cache status")
    IMPORT_CACHE = t_("ui.action.import_cache.title", "Import cache data")
    EXPORT_CACHE = t_("ui.action.export_cache.title", "Export cache data")
    EDIT_CACHE = t_("ui.action.edit_cache.title", "Edit cache data")

    # Miscellaneous
    NOT_AVAILABLE_TITLE = t_("ui.action.not_available.title", "Not Available")
    NOT_AVAILABLE_TEXT = t_(
        "ui.action.not_available.text",
        "That function is not currently available because the cache database is disabled.",
    )

    # Registered Script Variables
    VARIABLE_ALBUMARTISTS_NAMES = t_(
        key='variable.albumartists_names',
        text="The names of the album artists.",
    )
    VARIABLE_ALBUMARTISTS_SORT_NAMES = t_(
        key='variable.albumartists_sort_names',
        text="The sort names of the album artists.",
    )
    VARIABLE_ALBUMARTISTS_TYPES = t_(
        key='variable.albumartists_types',
        text="The types of the album artists, such as 'person' or 'group'.",
    )
    VARIABLE_ALBUMARTISTS_GENDERS = t_(
        key='variable.albumartists_genders',
        text="The genders of the album artists.",
    )
    VARIABLE_ALBUMARTISTS_BEGIN_DATES = t_(
        key='variable.albumartists_begin_dates',
        text=(
            "The dates when the album artists began, typically the birth date of a person or the "
            "formation date of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_BEGIN_LOCATIONS = t_(
        key='variable.albumartists_begin_locations',
        text=(
            "The locations where the album artists began, typically the birth place of a person or the "
            "formation place of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_BEGIN_COUNTRIES = t_(
        key='variable.albumartists_begin_countries',
        text=(
            "The countries where the album artists began, typically the birth country of a person or the "
            "formation country of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_END_DATES = t_(
        key='variable.albumartists_end_dates',
        text=(
            "The dates when the album artists ended, typically the death date of a person or the "
            "disbanding date of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_END_LOCATIONS = t_(
        key='variable.albumartists_end_locations',
        text=(
            "The locations where the album artists ended, typically the death place of a person or the "
            "disbanding place of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_END_COUNTRIES = t_(
        key='variable.albumartists_end_countries',
        text=(
            "The countries where the album artists ended, typically the death country of a person or the "
            "disbanding country of a group."
        ),
    )
    VARIABLE_ALBUMARTISTS_LOCATIONS = t_(
        key='variable.albumartists_locations',
        text="The current home locations of the album artists.",
    )
    VARIABLE_ALBUMARTISTS_COUNTRIES = t_(
        key='variable.albumartists_countries',
        text="The countries where the album artists are based.",
    )
    VARIABLE_ALBUMARTISTS_DISAMBIGUATIONS = t_(
        key='variable.albumartists_disambiguations',
        text="The disambiguation comments for the album artists, if any.",
    )
    VARIABLE_ALBUMARTISTS_WEBSITES = t_(
        key='variable.albumartists_websites',
        text="The websites of the album artists, if any.",
    )

    VARIABLE_ARTISTS_NAMES = t_(
        key='variable.artists_names',
        text=(
            "The names of the track artists. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_SORT_NAMES = t_(
        key='variable.artists_sort_names',
        text=(
            "The sort names of the track artists. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_TYPES = t_(
        key='variable.artists_types',
        text=(
            "The types of the track artists, such as 'person' or 'group'. Only available if the option to process "
            "track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_GENDERS = t_(
        key='variable.artists_genders',
        text=(
            "The genders of the track artists. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_BEGIN_DATES = t_(
        key='variable.artists_begin_dates',
        text=(
            "The dates when the track artists began, typically the birth date of a person or the formation date of a "
            "group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_BEGIN_LOCATIONS = t_(
        key='variable.artists_begin_locations',
        text=(
            "The locations where the track artists began, typically the birth place of a person or the formation place "
            "of a group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_BEGIN_COUNTRIES = t_(
        key='variable.artists_begin_countries',
        text=(
            "The countries where the track artists began, typically the birth country of a person or the formation "
            "country of a group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_END_DATES = t_(
        key='variable.artists_end_dates',
        text=(
            "The dates when the track artists ended, typically the death date of a person or the disbanding date of a "
            "group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_END_LOCATIONS = t_(
        key='variable.artists_end_locations',
        text=(
            "The locations where the track artists ended, typically the death place of a person or the disbanding place "
            "of a group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_END_COUNTRIES = t_(
        key='variable.artists_end_countries',
        text=(
            "The countries where the track artists ended, typically the death country of a person or the disbanding "
            "country of a group. Only available if the option to process track artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_LOCATIONS = t_(
        key='variable.artists_locations',
        text=(
            "The current home locations of the track artists. Only available if the option to process track artists "
            "is enabled."
        ),
    )
    VARIABLE_ARTISTS_COUNTRIES = t_(
        key='variable.artists_countries',
        text=(
            "The countries where the track artists are based. Only available if the option to process track artists "
            "is enabled."
        ),
    )
    VARIABLE_ARTISTS_DISAMBIGUATIONS = t_(
        key='variable.artists_disambiguations',
        text=(
            "The disambiguation comments for the track artists, if any. Only available if the option to process track "
            "artists is enabled."
        ),
    )
    VARIABLE_ARTISTS_WEBSITES = t_(
        key='variable.artists_websites',
        text=(
            "The websites of the track artists, if any. Only available if the option to process track artists is enabled."
        ),
    )
