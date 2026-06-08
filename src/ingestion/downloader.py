from src.clients.chesscom import ChessComClient
from ..storage.storage import archive_already_saved, save_raw_archive


def run(username: str) -> None:
    """
    Run the ingestion pipeline for a user.

    Fetches all monthly archives from Chess.com and saves any that are not
    already on disk. Skips archives whose raw file already exists.

    Args:
        username (str): Chess.com username.

    Returns:
        None
    """
    print("Download Started")

    client = ChessComClient()

    print(f"[INFO] Loading archives for {username}")

    archives = client.get_archives(username)

    pending = [url for url in archives if not archive_already_saved(username, url)]

    print(f"[INFO] Total archives: {len(archives)}")
    print(f"[INFO] Archives to fetch: {len(pending)}")

    for archive_url in pending:
        print(f"[FETCH] {archive_url}")

        data = client.get_archive_games(archive_url)

        path = save_raw_archive(username, archive_url, data)

        games = data.get("games", [])

        print(f"[SAVED] {path} ({len(games)} games)")

    print("[DONE] Ingestion complete")


if __name__ == "__main__":
    import sys

    username = sys.argv[1]
    run(username)
