"""
Humanize file sizes.
"""


def pretty_size(size: int) -> str:
    """
    Pretty print a file size.

    >>> pretty_size(0)
    '0 B'
    >>> pretty_size(1)
    '1 B'
    >>> pretty_size(1023)
    '1023 B'
    >>> pretty_size(1024)
    '1.00 KB'
    >>> pretty_size(1024 * 1024)
    '1.00 MB'
    >>> pretty_size(1024 * 1024 * 1024)
    '1.00 GB'
    >>> pretty_size(1024 * 1024 * 1024 * 1024)
    '1.00 TB'
    >>> pretty_size(1024 * 1024 * 1024 * 1024 * 1024)
    '1.00 PB'
    >>> pretty_size(1024 * 1024 * 1024 * 1024 * 1024 * 1024)
    '1024.00 PB'
    """
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    index = 0
    size_float = float(size)

    while size_float >= 1024 and index < len(units) - 1:
        size_float /= 1024
        index += 1

    if index == 0:
        return f"{size} B"
    return f"{size_float:.2f} {units[index]}"
