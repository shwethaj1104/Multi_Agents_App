"""Run from backend with: uv run python scripts/check_database.py. No model calls are made."""

from pymongo import MongoClient

from loandesk.core.settings import get_settings
from loandesk.infrastructure.database.connection_diagnostics import describe_mongodb_failure


# Check only database connectivity and print safe guidance; never print the URI or raw driver error.
def main() -> int:
    settings = get_settings()
    if not settings.mongodb_uri.get_secret_value():
        print("MONGODB_URI is blank. Fill it in backend/.env before checking Atlas.")
        return 1
    client = None
    try:
        client = MongoClient(
            settings.mongodb_uri.get_secret_value(),
            serverSelectionTimeoutMS=7000,
            connectTimeoutMS=5000,
        )
        client.admin.command("ping")
        print("MongoDB connectivity check passed. No model call was made.")
        return 0
    except Exception as error:
        print(describe_mongodb_failure(error, "connectivity check"))
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
