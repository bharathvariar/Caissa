import json
from pathlib import Path


def get_state_path(username: str) -> Path:
    """
    Get filesystem path for a user's ingestion state file.

    Args:
        username (str): Chess.com username.

    Returns:
        Path: Path to state.json for the user.
    """
    return Path(f"data/users/{username}/state.json")


def load_state(username: str) -> dict:
    """
    Load ingestion state for a user.

    Args:
        username (str): Chess.com username.

    Returns:
        dict: State dictionary. Empty dict if no state exists.
    """
    path = get_state_path(username)

    if not path.exists():
        return {}

    return json.loads(path.read_text())


def save_state(username: str, state: dict) -> None:
    """
    Save ingestion state for a user.

    Args:
        username (str): Chess.com username.
        state (dict): State data to persist.

    Returns:
        None
    """
    path = get_state_path(username)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(json.dumps(state, indent=2))
