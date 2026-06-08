from src.db.connection import get_connection


def win_rate_by_time_class(username: str) -> list[dict]:
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
