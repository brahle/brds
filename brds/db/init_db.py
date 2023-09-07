from datetime import time
from os.path import join
from sqlite3 import connect, Connection
from typing import Optional, Type, TYPE_CHECKING, Tuple

if TYPE_CHECKING:
    from types import TracebackType

from brds.core.environment import writer_folder_path

def initialize_db(conn: Connection):
    cursor = conn.cursor()

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS web_pages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL UNIQUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    cursor.execute('''
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
    ''')

    conn.commit()


class Database():
    def __init__(self: "Database", path: str) -> None:
        self.path = join(writer_folder_path(), path)
        self.connection = None

    def __enter__(self: "Database"):
        self.connection = connect(self.path)
        initialize_db(self.connection)
        return self

    def __exit__(
            self: "Database",
            exc_type: Optional[Type[BaseException]],
            exc_val: Optional[BaseException],
            exc_tb: Optional["TracebackType"]
    ) -> None:
        if self.connection:
            self.connection.close()

    def register_web_page(self: "Database", url: str) -> None:
        existing_id = self.get_url_id(url)
        if existing_id is not None:
            return existing_id

        cursor = self.connection.cursor()
        cursor.execute("INSERT INTO web_pages (url) VALUES (?)", (url,))
        new_id = cursor.lastrowid
        self.connection.commit()
        return new_id

    def get_url_id(self: "Database", url: str) -> Optional[int]:
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
        cursor = self.connection.cursor()
        cursor.execute(
            "INSERT INTO page_versions (web_page_id, source_name, source_file, dataset_name, content_file_path, status_code) VALUES (?, ?, ?, ?, ?, ?)",
            (url_id, source_name, source_file, dataset_name, content_file_path, status_code)
        )
        new_id = cursor.lastrowid
        self.connection.commit()
        return new_id

    def latest_download(self: "Database", url_id: int) -> Tuple[str, time]:
        cursor = self.connection.cursor()
        cursor.execute(
            """
            SELECT content_file_path, dataset_name, version_date
            FROM page_versions
            WHERE web_page_id=?
            ORDER BY version_date DESC
            LIMIT 1
            """,
            (url_id,)
        )
        result = cursor.fetchone()
        self.connection.commit()
        return result

    def latest_downloads(self: "Database"):
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
        cursor = self.connection.cursor()
        values = ('%' + url_like + '%',)
        cursor.execute(
            '''
            DELETE FROM page_versions
            WHERE web_page_id IN (SELECT id FROM web_pages WHERE url LIKE ?)
            ''',
            values,
        )

        cursor.execute('''DELETE FROM web_pages WHERE url LIKE ?''', values)
        self.connection.commit()
