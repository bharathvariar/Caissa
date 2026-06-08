import requests

BASE_URL = "https://api.chess.com/pub"

HEADERS = {
    "User-Agent": "Caissa/0.1"
}


class ChessComClient:
    """
    Client for interacting with the Chess.com Public API.
    """

    def __init__(self) -> None:
        self.session = requests.Session()
        self.session.headers.update(HEADERS)

    def get_archives(self, username: str) -> list[str]:
        """
        Fetch monthly archive URLs for a user.

        Args:
            username (str): Chess.com username.

        Returns:
            list[str]: Archive URLs.
        """
        url = f"{BASE_URL}/player/{username}/games/archives"

        response = self.session.get(url, timeout=30)
        response.raise_for_status()

        data = response.json()

        return data.get("archives", [])

    def get_archive_games(self, archive_url: str) -> dict:
        """
        Fetch games from a monthly archive.

        Args:
            archive_url (str): Monthly archive URL.

        Returns:
            dict: Raw Chess.com archive response.
        """
        response = self.session.get(archive_url, timeout=30)
        response.raise_for_status()

        return response.json()
