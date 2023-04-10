"""
Information about a dataset.
"""

from datetime import datetime

from brds.humanize import pretty_size


class DatasetInfo:
    """
    Information about a dataset.
    """

    def __init__(
        self: "DatasetInfo", module: str, name: str, timestamp: datetime, file_size: int, old_versions: int
    ) -> None:
        self.module = module
        self.name = name
        self.timestamp = timestamp
        self.file_size = file_size
        self.old_versions = old_versions

    def __repr__(self: "DatasetInfo") -> str:
        """
        String representation of the dataset info.

        >>> DatasetInfo("module", "name", datetime(2020, 1, 1), 0, 0)
        <DatasetInfo(module='module', name='name', timestamp=2020-01-01 00:00:00, file_size=0, old_versions=0)>
        """
        return (
            f"<DatasetInfo(module='{self.module}', name='{self.name}', "
            f"timestamp={self.timestamp}, file_size={self.file_size}, "
            f"old_versions={self.old_versions})>"
        )

    def __str__(self: "DatasetInfo") -> str:
        """
        String representation of the dataset info.

        >>> DatasetInfo("module", "name", datetime(2020, 1, 1), 0, 0)
        <DatasetInfo(module='module', name='name', timestamp=2020-01-01 00:00:00, file_size=0, old_versions=0)>
        """
        return self.__repr__()

    @property
    def pretty_file_size(self: "DatasetInfo") -> str:
        """
        Pretty print the file size.

        >>> DatasetInfo("module", "name", datetime(2020, 1, 1), 0, 0).pretty_file_size
        '0 B'
        >>> DatasetInfo("module", "name", datetime(2020, 1, 1), 1024, 0).pretty_file_size
        '1.00 KB'
        """
        return pretty_size(self.file_size)
