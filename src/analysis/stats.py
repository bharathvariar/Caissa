from src.db.connection import get_connection


def win_rate_by_time_class(username: str) -> list[dict]:
    """
    Calculate win rate grouped by time class for a user.

    Args:
        username (str): Chess.com username.

    Returns:
        list[dict]: One dict per time class with keys: time_class, games, wins, win_rate.
    """
    sql = """
        SELECT
            time_class,
            COUNT(*) AS games,
            SUM(
                CASE
                    WHEN white_username = ? AND white_result = 'win' THEN 1
                    WHEN black_username = ? AND black_result = 'win' THEN 1
                    ELSE 0
                END
            ) AS wins
        FROM games
        WHERE white_username = ? OR black_username = ?
        GROUP BY time_class
        ORDER BY games DESC
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (username, username, username, username)).fetchall()
    return [
        {**dict(r), "win_rate": round(r["wins"] / r["games"] * 100, 1)}
        for r in rows
    ]


def rating_over_time(username: str) -> list[dict]:
    """
    Calculate average rating per calendar month for a user.

    Args:
        username (str): Chess.com username.

    Returns:
        list[dict]: One dict per month with keys: month (YYYY-MM), avg_rating.
    """
    sql = """
        SELECT
            strftime('%Y-%m', datetime(end_time, 'unixepoch')) AS month,
            AVG(
                CASE
                    WHEN white_username = ? THEN white_rating
                    ELSE black_rating
                END
            ) AS avg_rating
        FROM games
        WHERE white_username = ? OR black_username = ?
        GROUP BY month
        ORDER BY month
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (username, username, username)).fetchall()
    return [{"month": r["month"], "avg_rating": round(r["avg_rating"])} for r in rows]


def top_openings(username: str, limit: int = 10) -> list[dict]:
    """
    Return the most frequently played openings for a user with win rates.

    Args:
        username (str): Chess.com username.
        limit (int): Maximum number of openings to return. Defaults to 10.

    Returns:
        list[dict]: One dict per opening with keys: eco_url, games, wins, win_rate.
    """
    sql = """
        SELECT
            eco_url,
            COUNT(*) AS games,
            SUM(
                CASE
                    WHEN white_username = ? AND white_result = 'win' THEN 1
                    WHEN black_username = ? AND black_result = 'win' THEN 1
                    ELSE 0
                END
            ) AS wins
        FROM games
        WHERE (white_username = ? OR black_username = ?)
          AND eco_url IS NOT NULL
        GROUP BY eco_url
        ORDER BY games DESC
        LIMIT ?
    """
    with get_connection() as conn:
        rows = conn.execute(sql, (username, username, username, username, limit)).fetchall()
    return [
        {**dict(r), "win_rate": round(r["wins"] / r["games"] * 100, 1)}
        for r in rows
    ]
