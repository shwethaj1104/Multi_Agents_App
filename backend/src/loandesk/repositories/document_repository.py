import json
import sqlite3
from pathlib import Path
from typing import Protocol

from pymongo import MongoClient, ReturnDocument

from loandesk.domain.contracts import DomainError


class DocumentRepository(Protocol):
    # Retrieve an application/review record by its opaque server identifier.
    def get(self, collection: str, identifier: str) -> dict | None: ...

    # List records using exact-match filters; caller input never supplies operator keys.
    def list(self, collection: str, filters: dict | None = None) -> list[dict]: ...

    # Insert an immutable initial record; return false on a duplicate identifier.
    def insert(self, collection: str, value: dict) -> bool: ...

    # Replace only the expected record version to prevent stale concurrent changes.
    def replace(self, collection: str, value: dict, expected_version: int) -> bool: ...

    # Release external storage resources when the application shuts down.
    def close(self) -> None: ...


class SqliteDocumentRepository:
    # Create a durable local document store used for offline development and isolated tests.
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute("PRAGMA journal_mode=WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS records (collection TEXT, id TEXT, "
                "version INTEGER, body TEXT, PRIMARY KEY(collection,id))"
            )

    # Open short transactions with a busy timeout so parallel specialist events can persist safely.
    def _connection(self):
        return sqlite3.connect(self.path, timeout=30)

    # Return a decoded record without exposing the storage-specific envelope.
    def get(self, collection: str, identifier: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT body FROM records WHERE collection=? AND id=?", (collection, identifier)
            ).fetchone()
        return json.loads(row[0]) if row else None

    # Apply simple equality filters consistently with the MongoDB adapter.
    def list(self, collection: str, filters: dict | None = None) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT body FROM records WHERE collection=? ORDER BY rowid DESC", (collection,)
            ).fetchall()
        values = [json.loads(row[0]) for row in rows]
        return [
            value for value in values if all(value.get(k) == v for k, v in (filters or {}).items())
        ]

    # Insert once; conflict means another operation already created the same record.
    def insert(self, collection: str, value: dict) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "INSERT OR IGNORE INTO records VALUES (?,?,?,?)",
                (collection, value["id"], value.get("version", 1), json.dumps(value)),
            )
            return cursor.rowcount == 1

    # Compare versions in SQL so competing human decisions cannot both win.
    def replace(self, collection: str, value: dict, expected_version: int) -> bool:
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE records SET body=?,version=? WHERE collection=? AND id=? AND version=?",
                (json.dumps(value), value["version"], collection, value["id"], expected_version),
            )
            return cursor.rowcount == 1

    # SQLite connections are scoped to each operation and need no persistent resource cleanup.
    def close(self) -> None:
        return None


class MongoDocumentRepository:
    # Connect to the configured database; failures never silently switch to a local store.
    def __init__(self, uri: str, database: str):
        self.client = MongoClient(uri, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000)
        try:
            self.client.admin.command("ping")
            self.database = self.client[database]
            for collection in ("applications", "reviews", "experiments", "budgets"):
                self.database[collection].create_index("id", unique=True)
            self.database.reviews.create_index([("case_id", 1), ("updated_at", -1)])
        except Exception:
            self.client.close()
            raise

    # Strip MongoDB's internal ObjectId before returning JSON-compatible records.
    def get(self, collection: str, identifier: str) -> dict | None:
        return self.database[collection].find_one({"id": identifier}, {"_id": 0})

    # Query server-owned collection names and equality filters only.
    def list(self, collection: str, filters: dict | None = None) -> list[dict]:
        return list(
            self.database[collection].find(filters or {}, {"_id": 0}).sort("created_at", -1)
        )

    # Insert an initial record while treating a duplicate key as an idempotent conflict.
    def insert(self, collection: str, value: dict) -> bool:
        from pymongo.errors import DuplicateKeyError

        try:
            self.database[collection].insert_one(dict(value))
            return True
        except DuplicateKeyError:
            return False

    # Atomically replace the expected version; this guards approvals and budget reservations.
    def replace(self, collection: str, value: dict, expected_version: int) -> bool:
        return (
            self.database[collection].find_one_and_replace(
                {"id": value["id"], "version": expected_version},
                dict(value),
                projection={"_id": 0},
                return_document=ReturnDocument.AFTER,
            )
            is not None
        )

    # Close the shared database client after the server finishes its work.
    def close(self) -> None:
        self.client.close()


# Apply a small atomic mutation with retries; never overwrite a newer decision or event.
def update_record(repository: DocumentRepository, collection: str, identifier: str, change) -> dict:
    for _ in range(30):
        current = repository.get(collection, identifier)
        if current is None:
            raise DomainError("Record not found.", 404)
        expected = current.get("version", 1)
        updated = change(dict(current))
        updated["version"] = expected + 1
        if repository.replace(collection, updated, expected):
            return updated
    raise DomainError("This record is busy. Refresh and try again.", 409)
