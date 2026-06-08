import json
import sys

from .stats import win_rate_by_time_class, rating_over_time, top_openings

COMMANDS = {
    "win-rate": win_rate_by_time_class,
    "rating": rating_over_time,
    "openings": top_openings,
}


def main() -> None:
    if len(sys.argv) < 3 or sys.argv[2] not in COMMANDS:
        print(f"Usage: python -m src.analysis.cli <username> <{'|'.join(COMMANDS)}>")
        sys.exit(1)

    username, command = sys.argv[1], sys.argv[2]
    result = COMMANDS[command](username)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
