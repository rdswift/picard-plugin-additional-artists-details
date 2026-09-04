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

from collections.abc import Generator
import csv
import json
import os
import sqlite3

from .common import SharedVars
from .const import (
    DB_DIR,
    DB_FILE,
)
from .entities import (
    AreaEntity,
    AreaType,
    ArtistEntity,
)
from .misc_utils import (
    is_valid_country_code,
    is_valid_mbid,
)


class DatabaseUtils:
    """Utility functions for working with the plugin's database."""

    DB_VERSION: int = 1

    _INSERT_ARTIST: str = (
        "INSERT OR REPLACE INTO artists (mbid, name, sort, type, gender, area, begin, begin_area, "
        "end, end_area, disambiguation) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)"
    )

    _INSERT_AREA: str = "INSERT OR REPLACE INTO areas (mbid, parent, name, country, type) VALUES (?, ?, ?, ?, ?)"

    _SELECT_ARTIST: str = (
        "SELECT mbid, name, sort, type, gender, area, begin, begin_area, end, end_area, disambiguation FROM artists"
    )

    _SELECT_AREA: str = "SELECT mbid, parent, name, country, type FROM areas"

    _DELETE_ARTIST: str = "DELETE FROM artists WHERE mbid=?"

    @classmethod
    def log_error(cls, fcn: str, ex: Exception) -> None:
        """Logs an error message.

        Args:
            fcn (str): Name of the function or method where the error occurred.
            ex (Exception): Exception raised.
        """
        SharedVars.api.logger.error(f"Error encountered in '{fcn}': {ex}")

    @classmethod
    def update_database_schema(cls) -> None:
        """Update the database schema to the latest version.

        This method checks the current version of the database and applies any necessary schema updates.
        """
        current_version = cls.get_db_version()

        if current_version >= cls.DB_VERSION:
            return  # Database is already up-to-date

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                # # Example of a schema update for version 2
                # if current_version < 2:
                #     if api:
                #         api.logger.debug("Updating database schema to version 2.")
                #     cursor.execute("ALTER TABLE artists ADD COLUMN new_column TEXT;")
                #     conn.commit()
                #     cls.set_db_version(2)
                #     current_version = 2  # Update current_version after applying the update
                # # Example of a schema update for version 3
                # if current_version < 3:
                #     if api:
                #         api.logger.debug("Updating database schema to version 3.")
                #     cursor.execute("ALTER TABLE artists ADD COLUMN new_column TEXT;")
                #     conn.commit()
                #     cls.set_db_version(3)
                #     current_version = 3  # Update current_version after applying the update
                cursor.close()
        except sqlite3.Error as ex:
            cls.log_error('update_database_schema()', ex)

    @classmethod
    def get_db_version(cls) -> int:
        """Get the current version of the database.

        Returns:
            int: The current version of the database.
        """
        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(version) FROM db_version;")
                result = cursor.fetchone()
                return result[0] if result else 0
        except sqlite3.Error as ex:
            cls.log_error('get_db_version()', ex)
        return cls.DB_VERSION

    @classmethod
    def set_db_version(cls, version: int) -> None:
        """Set the version of the database.

        Args:
            version (int): The version number to set for the database.
        """
        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute("INSERT OR REPLACE INTO db_version (version) VALUES (?);", (version,))
                conn.commit()
        except sqlite3.Error as ex:
            cls.log_error('set_db_version()', ex)

    @classmethod
    def connect_to_database(cls) -> sqlite3.Connection:
        """Connect to the plugin's database.

        Returns:
            sqlite3.Connection: A connection object to the database.
        """
        return sqlite3.connect(DB_FILE)

    @classmethod
    def initialize_database(cls) -> None:
        """Initialize the plugin's database.

        This method creates the database file and the necessary tables if they do not already exist.
        """
        if os.path.exists(DB_FILE):
            return  # Database already exists, no need to initialize

        try:
            os.makedirs(DB_DIR, exist_ok=True)

            with cls.connect_to_database() as conn:
                cursor = conn.cursor()

                # Table columns:
                #   mbid:           MBID for the artist
                #   name:           Name of the artist
                #   sort:           Sort name for the artist
                #   type:           Type of artist
                #   gender:         Gender of the artist
                #   area:           MBID for the current area
                #   begin:          Begin date for the artist
                #   begin_area:     MBID of the begin area
                #   end:            End date for the Artist
                #   end_area:       MBID of the end area
                #   disambiguation: Disambiguation comment
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS artists (
                        mbid TEXT PRIMARY KEY,
                        name TEXT NOT NULL,
                        sort TEXT,
                        type TEXT,
                        gender TEXT,
                        area TEXT,
                        begin TEXT,
                        begin_area TEXT,
                        end TEXT,
                        end_area TEXT,
                        disambiguation TEXT
                    );
                ''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_name ON artists(name);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_artists_sort ON artists(sort);")
                conn.commit()

                # Table columns:
                #   mbid:       MBID of the area
                #   parent:     MBID of the area's parent
                #   name:       Name of the area
                #   country:    Two-character country code if the area is a country
                #   type:       MBID of the area's type
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS areas (
                        mbid TEXT PRIMARY KEY,
                        parent TEXT,
                        name TEXT NOT NULL,
                        country TEXT,
                        type TEXT
                    );
                ''')
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_areas_name ON areas(name);")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_areas_parent ON areas(parent);")
                conn.commit()

                cursor.execute("DROP TABLE IF EXISTS db_version;")
                conn.commit()
                cursor.execute('''
                    CREATE TABLE IF NOT EXISTS db_version (
                        version INTEGER PRIMARY KEY
                    );
                ''')
                conn.commit()

        except OSError as ex:
            cls.log_error('initialize_database()', ex)
            return

        except sqlite3.Error as ex:
            cls.log_error('initialize_database()', ex)
            try:
                os.remove(DB_FILE)
            except OSError:
                pass
            return

        cls.set_db_version(1)
        cls.update_database_schema()

    @classmethod
    def import_from_json(cls, filename: str, save_artists: bool | None = None) -> None:
        """Import artist and area data from a JSON file into the database.

        Args:
            json_file (str): The path to the JSON file containing artist and area data.
            save_artists (bool, optional): Determines whether artist information is imported. Defaults to current configuration setting.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        if not os.path.exists(filename):
            raise FileNotFoundError(f"JSON file '{filename}' not found.")

        if save_artists is None:
            save_artists = SharedVars.save_artists

        with cls.connect_to_database() as conn:
            cursor = conn.cursor()

            with open(filename, 'r') as f:
                json_data = json.load(f)

            if save_artists:
                for mbid, artist in json_data.get('artist', {}).items():
                    if not is_valid_mbid(mbid):
                        continue  # Invalid artist MBID

                    cursor.execute(
                        cls._INSERT_ARTIST,
                        (
                            mbid,
                            artist.get('name', 'Unknown Artist'),
                            artist.get('sort-name', 'Unknown Artist'),
                            artist.get('type', 'Unknown'),
                            artist.get('gender', ''),
                            artist.get('area', ''),
                            artist.get('begin', ''),
                            artist.get('begin-area', ''),
                            artist.get('end', ''),
                            artist.get('end-area', ''),
                            artist.get('disambiguation', ''),
                        ),
                    )
                conn.commit()

            for mbid, area in json_data.get('area', {}).items():
                cursor.execute(
                    cls._INSERT_AREA,
                    (
                        mbid,
                        area.get('parent', ''),
                        area.get('name', 'Unknown Area'),
                        area.get('country', ''),
                        area.get('area_type', ''),
                    ),
                )
            conn.commit()

    @classmethod
    def import_from_csv(cls, filename: str, save_artists: bool | None = None) -> None:
        """Import artist and area data from a CSV file into the database.

        Args:
            csv_file (str): The path to the CSV file containing artist and area data.
            save_artists (bool, optional): Determines whether artist information is imported. Defaults to current configuration setting.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        if not os.path.exists(filename):
            raise FileNotFoundError(f"CSV file '{filename}' not found.")

        if save_artists is None:
            save_artists = SharedVars.save_artists

        csv.register_dialect('custom', delimiter=',', doublequote=False, escapechar='\\', lineterminator='\n')
        with cls.connect_to_database() as conn:
            cursor = conn.cursor()

            with open(filename, 'r', newline='', encoding='utf-8') as f:
                reader = csv.reader(f, dialect='custom')

                for row in reader:
                    if row[0] not in ('artist', 'area'):
                        continue  # Skip rows that are not artist or area data

                    # Area row processing
                    if row[0] == 'area':
                        # Row columns:
                        #   0.  Data type (area)
                        #   1.  MBID of the area
                        #   2.  MBID of the area's parent
                        #   3.  Name of the area
                        #   4.  Two-character country code if the area is a country
                        #   5.  MBID of the area's type
                        if len(row) < 6:
                            continue  # Skip area rows that don't have enough columns
                        if not is_valid_mbid(row[1]):
                            continue  # Invalid area MBID
                        if row[2] and not is_valid_mbid(row[2]):
                            continue  # Invalid parent area MBID (empty string allowed for country records)
                        if not row[3].strip():
                            continue  # Missing area name
                        if row[4] and not is_valid_country_code(row[4]):
                            continue  # Invalid country code
                        if row[5] not in AreaType.all_mbids:
                            continue  # Invalid area type MBID
                        cursor.execute(cls._INSERT_AREA, (row[1], row[2], row[3], row[4], row[5]))

                    # Artist row processing
                    if not save_artists:
                        continue

                    # Row columns:
                    #    0. Data type (artist)
                    #    1. MBID for the artist
                    #    2. Name of the artist
                    #    3. Sort name for the artist
                    #    4. Type of artist
                    #    5. Gender of the artist
                    #    6. MBID for the current area
                    #    7. Begin date for the artist
                    #    8. MBID of the begin area
                    #    9. End date for the Artist
                    #   10. MBID of the end area
                    #   11. Disambiguation comment
                    if len(row) < 12:
                        continue  # Skip artist rows that don't have enough columns
                    if not is_valid_mbid(row[1]):
                        continue  # Invalid artist MBID
                    if not row[2].strip():
                        continue  # Missing artist name
                    if not row[3].strip():
                        continue  # Missing artist sort name
                    if not row[4].strip():
                        continue  # Missing artist type
                    if row[6] and not is_valid_mbid(row[6]):
                        continue  # Invalid area MBID
                    if row[8] and not is_valid_mbid(row[8]):
                        continue  # Invalid area MBID
                    if row[10] and not is_valid_mbid(row[10]):
                        continue  # Invalid area MBID
                    cursor.execute(
                        cls._INSERT_ARTIST,
                        (row[1], row[2], row[3], row[4], row[5], row[6], row[7], row[8], row[9], row[10], row[11]),
                    )

            conn.commit()

    @classmethod
    def export_to_csv(cls, filename: str, save_artists: bool | None = None) -> None:
        """Export artist and area data to a CSV file from the database.

        Args:
            filename (str): The path of the CSV file to write the artist and area data.
            save_artists (bool, optional): Determines whether artist information is exported. Defaults to current configuration setting.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        csv.register_dialect('custom', delimiter=',', doublequote=False, escapechar='\\', lineterminator='\n')

        if save_artists is None:
            save_artists = SharedVars.save_artists

        with open(filename, 'w', newline='\n', encoding='utf-8') as f:
            writer = csv.writer(f, dialect='custom', quoting=csv.QUOTE_ALL)
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()

                # Write area records
                writer.writerow(
                    [
                        "Area information",
                        "MBID of the area",
                        "MBID of the area's parent",
                        "Name of the area",
                        "Two-character country code if the area is a country",
                        "MBID of the area's type",
                        "Area type text",
                    ]
                )
                cursor.execute(cls._SELECT_AREA + " ORDER BY name ASC;")
                row = cursor.fetchone()
                while row is not None:
                    writer.writerow(('area',) + row + (AreaType.titles.get(row[4], 'Unknown area type'),))
                    row = cursor.fetchone()

                # Write artist records
                if save_artists:
                    writer.writerow(
                        [
                            "Artist information",
                            "MBID for the artist",
                            "Name of the artist",
                            "Sort name for the artist",
                            "Type of artist",
                            "Gender of the artist",
                            "MBID for the current area",
                            "Begin date for the artist",
                            "MBID of the begin area",
                            "End date for the Artist",
                            "MBID of the end area",
                            "Disambiguation comment",
                        ]
                    )
                    cursor.execute(cls._SELECT_ARTIST + " ORDER BY sort ASC;")
                    row = cursor.fetchone()
                    while row is not None:
                        writer.writerow(('artist',) + row)
                        row = cursor.fetchone()

    @classmethod
    def get_area(cls, mbid: str) -> AreaEntity | None:
        """Get an area record.

        Args:
            mbid (str): MBID of the area to retrieve.

        Returns:
            AreaEntity | None: Area information if found, otherwise None.
        """
        if not os.path.exists(DB_FILE):
            return None  # Database does not exist

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(cls._SELECT_AREA + " WHERE mbid=?;", (mbid,))
                row = cursor.fetchone()
            return (
                AreaEntity(
                    mbid=row[0],
                    name=row[2],
                    type=row[4],
                    parent=row[1],
                    country=row[3],
                )
                if row
                else None
            )

        except sqlite3.Error as ex:
            cls.log_error('get_area()', ex)
            return None

    @classmethod
    def get_artist(cls, mbid: str) -> ArtistEntity | None:
        """Get an artist record.

        Args:
            mbid (str): MBID of the artist to retrieve.

        Returns:
            ArtistEntity | None: Artist information if found, otherwise None.
        """
        if not os.path.exists(DB_FILE):
            return None  # Database does not exist

        if not SharedVars.save_artists:
            return None

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(cls._SELECT_ARTIST + " WHERE mbid=?;", (mbid,))
                row = cursor.fetchone()
            return cls._artist_from_row(row) if row else None

        except sqlite3.Error as ex:
            cls.log_error('get_artist()', ex)
            return None

    @classmethod
    def set_area(cls, area: AreaEntity) -> bool:
        """Set an area record.

        Args:
            area (AreaEntity): Area information to set.

        Returns:
            bool: True on success, otherwise False.
        """
        if not os.path.exists(DB_FILE):
            return False  # Database does not exist

        if not is_valid_mbid(area.mbid):
            return False  # Invalid area MBID
        if not area.name.strip():
            return False  # Missing area name
        if area.type not in AreaType.all_mbids:
            return False  # Invalid area type MBID
        if area.parent and not is_valid_mbid(area.parent):
            return False  # Invalid parent MBID
        if area.country and not is_valid_country_code(area.country):
            return False  # Invalid country code

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(cls._INSERT_AREA, (area.mbid, area.parent, area.name, area.country, area.type))
                conn.commit()

        except sqlite3.Error as ex:
            cls.log_error('set_area()', ex)
            return False

        return True

    @classmethod
    def set_artist(cls, artist: ArtistEntity) -> bool:
        """Set an artist record.

        Args:
            artist (ArtistEntity): Artist information to set.

        Returns:
            bool: True on success, otherwise False.
        """
        if not os.path.exists(DB_FILE):
            return False  # Database does not exist

        if not SharedVars.save_artists:
            return False  # Saving artists not enabled
        if not is_valid_mbid(artist.mbid):
            return False  # Invalid artist MBID
        if not artist.name.strip():
            return False  # Missing artist name
        if not artist.sort.strip():
            return False  # Missing artist sort name
        if artist.area and not is_valid_mbid(artist.area):
            return False  # Invalid area MBID
        if artist.begin_area and not is_valid_mbid(artist.begin_area):
            return False  # Invalid begin area MBID
        if artist.end_area and not is_valid_mbid(artist.end_area):
            return False  # Invalid end area MBID

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    cls._INSERT_ARTIST,
                    (
                        artist.mbid,
                        artist.name,
                        artist.sort,
                        artist.type,
                        artist.gender,
                        artist.area,
                        artist.begin,
                        artist.begin_area,
                        artist.end,
                        artist.end_area,
                        artist.disambiguation,
                    ),
                )
                conn.commit()

        except sqlite3.Error as ex:
            cls.log_error('set_artist()', ex)
            return False

        return True

    @classmethod
    def remove_artists(cls, mbids: list[str]) -> None:
        """Remove artists from the database.

        Args:
            mbids (list[str]): List of the artist MBIDs to remove.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                for mbid in mbids:
                    cursor.execute(cls._DELETE_ARTIST, (mbid,))
                conn.commit()

        except sqlite3.Error as ex:
            cls.log_error('remove_artists()', ex)

    @staticmethod
    def _artist_from_row(row) -> ArtistEntity:
        return ArtistEntity(
            mbid=row[0],
            name=row[1],
            sort=row[2],
            type=row[3],
            gender=row[4],
            area=row[5],
            begin=row[6],
            begin_area=row[7],
            end=row[8],
            end_area=row[9],
            disambiguation=row[10],
        )

    @staticmethod
    def _area_from_row(row) -> AreaEntity:
        return AreaEntity(
            mbid=row[0],
            name=row[2],
            type=row[4],
            parent=row[1],
            country=row[3],
        )

    @classmethod
    def get_all_artists(cls) -> Generator[ArtistEntity, None, None]:
        """Get all artists from the database.

        Yields:
            Generator[ArtistEntity]: Artist entity information.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(cls._SELECT_ARTIST + " ORDER BY sort ASC;")
                row = cursor.fetchone()
                while row is not None:
                    yield cls._artist_from_row(row)
                    row = cursor.fetchone()

        except sqlite3.Error as ex:
            cls.log_error('get_all_artists()', ex)

    @classmethod
    def get_counts(cls) -> tuple[int | None, int | None]:
        """Get the number of artist and area entries in the database.

        Returns:
            tuple[int | None, int | None]: Tuple of the number of artists and areas, or None for the entity on error.
        """
        if not os.path.exists(DB_FILE):
            return (None, None)  # Database does not exist

        artist = None
        area = None

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(mbid) FROM artists;")
                row = cursor.fetchone()
                if row:
                    artist = int(row[0])

        except sqlite3.Error as ex:
            cls.log_error('get_counts()', ex)

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(mbid) FROM areas;")
                row = cursor.fetchone()
                if row:
                    area = int(row[0])

        except sqlite3.Error as ex:
            cls.log_error('get_counts()', ex)

        return (artist, area)

    @classmethod
    def get_orphan_areas_count(cls) -> tuple[int, int]:
        """Get the number of missing parents and orphan areas in the database.

        Returns:
            tuple[int, int]: Tuple containing the number of missing parents and the number of orphan area records.
        """
        if not os.path.exists(DB_FILE):
            return (0, 0)

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT COUNT(DISTINCT parent), COUNT(mbid) FROM areas WHERE parent <> "" AND parent NOT IN (SELECT mbid from areas);'
                )
                row = cursor.fetchone()
                if row:
                    return (int(row[0]), int(row[1]))

        except sqlite3.Error as ex:
            cls.log_error('get_orphan_areas_count()', ex)

        return (0, 0)

    @classmethod
    def get_missing_parent_areas(cls) -> Generator[str, None, None]:
        """Get the missing parent areas in the database.

        Yields:
            Generator[str]: Missing parent area MBIDs.
        """
        if not os.path.exists(DB_FILE):
            return  # Database does not exist

        try:
            with cls.connect_to_database() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    'SELECT DISTINCT parent FROM areas WHERE parent <> "" AND parent NOT IN (SELECT mbid from areas);'
                )
                row = cursor.fetchone()
                while row is not None:
                    yield row[0]
                    row = cursor.fetchone()

        except sqlite3.Error as ex:
            cls.log_error('get_orphan_areas()', ex)
