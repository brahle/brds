from datetime import time
from json import dumps
from os.path import join
from sqlite3 import Connection, connect
from typing import TYPE_CHECKING, Any, Dict, Iterable, Optional, Tuple, Type

if TYPE_CHECKING:
    from types import TracebackType

from brds.core.environment import writer_folder_path


def initialize_db(conn: Connection):
    cursor = conn.cursor()

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS web_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS page_versions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            web_page_id INTEGER REFERENCES web_pages(id),
            source_name TEXT NOT NULL,
            source_file TEXT NOT NULL,
            status_code INTEGER,
            dataset_name TEXT,
            content_file_path TEXT,
            version_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS variables (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            variable_name TEXT,
            variable_value TEXT,
            UNIQUE (variable_name, variable_value)
        )
        """
    )

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS variables_to_web_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            web_page_id INTEGER REFERENCES web_pages(id),
            variable_id INTEGER REFERENCES variables(id),
            UNIQUE (web_page_id, variable_id)
        )
        """
    )
    conn.commit()


class Database:
    def __init__(self: "Database", path: str) -> None:
        self.path = join(writer_folder_path(), path)
        self.connection: Optional[Connection] = None

    def __enter__(self: "Database"):
        self.connection = connect(self.path)
        initialize_db(self.connection)
        return self

    def __exit__(
        self: "Database",
        exc_type: Optional[Type[BaseException]],
        exc_val: Optional[BaseException],
        exc_tb: Optional["TracebackType"],
    ) -> None:
        if self.connection:
            self.connection.close()
            self.connection = None

    def register_web_page(self: "Database", url: str) -> int:
        assert self.connection is not None

        existing_id = self.get_url_id(url)
        if existing_id is not None:
            return existing_id

        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO web_pages (url) VALUES (?)", (url,))
        new_id = cursor.lastrowid
        self.connection.commit()
        assert new_id is not None
        return new_id

    def get_url_id(self: "Database", url: str) -> Optional[int]:
        assert self.connection is not None

        cursor = self.connection.cursor()
        cursor.execute("SELECT id FROM web_pages WHERE url=?", (url,))
        result = cursor.fetchone()
        self.connection.commit()
        if result:
            return result[0]
        return None

    def register_download(
        self: "Database",
        url_id: int,
        source_name: str,
        source_file: str,
        dataset_name: str,
        content_file_path: str,
        status_code: int,
    ) -> int:
        assert self.connection is not None

        cursor = self.connection.cursor()
        cursor.execute(
            """
            INSERT INTO page_versions
            (web_page_id, source_name, source_file, dataset_name, content_file_path, status_code)
            VALUES
            (?, ?, ?, ?, ?, ?)
            """,
            (url_id, source_name, source_file, dataset_name, content_file_path, status_code),
        )
        new_id = cursor.lastrowid
        self.connection.commit()
        assert new_id is not None
        return new_id

    def latest_download(self: "Database", url_id: int) -> Tuple[str, time]:
        assert self.connection is not None

        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT content_file_path, dataset_name, version_date
            FROM page_versions
            WHERE web_page_id=?
            ORDER BY version_date DESC
            LIMIT 1
            """,
            (url_id,),
        )
        result = cursor.fetchone()
        self.connection.commit()
        return result

    def latest_downloads(self: "Database"):
        assert self.connection is not None

        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT pv.*
            FROM page_versions AS pv
            JOIN (
                SELECT web_page_id, MAX(version_date) AS latest_date
                FROM page_versions
                GROUP BY web_page_id
            ) AS latest
            ON pv.web_page_id = latest.web_page_id AND pv.version_date = latest.latest_date;
            """
        )
        self.connection.commit()
        return cursor.fetchall()

    def delete_urls_like(self: "Database", url_like: str) -> None:
        assert self.connection is not None

        cursor = self.connection.cursor()
        values = ("%" + url_like + "%",)
        cursor.execute(
            """
            DELETE FROM page_versions
            WHERE web_page_id IN (SELECT id FROM web_pages WHERE url LIKE ?)
            """,
            values,
        )

        cursor.execute("""DELETE FROM web_pages WHERE url LIKE ?""", values)
        self.connection.commit()

    def set_vriables(self: "Database", url_id: int, variables: Dict[str, Any]) -> None:
        assert self.connection is not None

        cursor = self.connection.cursor()
        cursor.executemany(
            "INSERT OR IGNORE INTO variables (variable_name, variable_value) VALUES (?, ?)", serialize(variables)
        )
        cursor.execute("DELETE FROM variables_to_web_pages WHERE web_page_id = ?", (url_id,))
        cursor.executemany(
            """
            INSERT OR IGNORE INTO variables_to_web_pages (web_page_id, variable_id)
            SELECT ?, id
            FROM variables
            WHERE variable_name = ? AND variable_value = ?
            """,
            [(url_id, value[0], value[1]) for value in serialize(variables)],
        )
        self.connection.commit()


def serialize(variables: Dict[str, Any]) -> Iterable[Tuple[str, str]]:
    for key, value in variables.items():
        if isinstance(value, str):
            yield (key, value)
        else:
            yield (key, dumps(value))
