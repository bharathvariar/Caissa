from src.clients.chesscom import ChessComClient
from .state import load_state, save_state


def get_new_archives(
    all_archives: list[str],
    last_archive: str | None,
) -> list[str]:
    if not last_archive:
        return all_archives

    try:
        idx = all_archives.index(last_archive)
        return all_archives[idx + 1 :]
    except ValueError:
        return all_archives

def run(username: str) -> None:
    """
    Run the ingestion pipeline for a user.

    Args:
        username (str): Chess.com username.

    Returns:
        None
    """
    print("Download Started")

    client = ChessComClient()

    state = load_state(username)
    last_archive = state.get("last_archive_url")

    print(f"[INFO] Loading archives for {username}")

    archives = client.get_archives(username)

    new_archives = get_new_archives(
        archives,
        last_archive,
    )

    print(f"[INFO] Total archives: {len(archives)}")
    print(f"[INFO] New archives to process: {len(new_archives)}")

    for archive_url in new_archives:
        print(f"[FETCH] {archive_url}")

        data = client.get_archive_games(archive_url)

        games = data.get("games", [])

        print(f"[INFO] Games in archive: {len(games)}")

        save_state(
            username,
            {
                "last_archive_url": archive_url,
            },
        )

    print("[DONE] Ingestion complete")

if __name__ == "__main__":
    import sys

    username = sys.argv[1]
    run(username)
