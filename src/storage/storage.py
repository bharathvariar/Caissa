import json
from pathlib import Path


def _raw_path(username: str, archive_url: str) -> Path:
    """
    Derive the raw storage path from an archive URL.

    Archive URLs end in .../games/{year}/{month}.

    Args:
        username (str): Chess.com username.
        archive_url (str): Monthly archive URL.

    Returns:
        Path: Destination path for the raw JSON file.
    """
    parts = archive_url.rstrip("/").split("/")
    year, month = parts[-2], parts[-1]
    return Path(f"data/users/{username}/raw/{year}-{month.zfill(2)}.json")


def archive_already_saved(username: str, archive_url: str) -> bool:
    """
    Check whether a raw archive file already exists on disk.

    Args:
        username (str): Chess.com username.
        archive_url (str): Monthly archive URL.

    Returns:
        bool: True if the file exists, False otherwise.
    """
    return _raw_path(username, archive_url).exists()


def save_raw_archive(username: str, archive_url: str, data: dict) -> Path:
    """
    Persist a raw Chess.com archive response to disk.

    Writes data/users/{username}/raw/{year}-{month}.json.
    Overwrites if the file already exists (idempotent content).

    Args:
        username (str): Chess.com username.
        archive_url (str): Monthly archive URL used to derive the filename.
        data (dict): Raw archive response from Chess.com.

    Returns:
        Path: Path where the file was written.
    """
    path = _raw_path(username, archive_url)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))
    return path
