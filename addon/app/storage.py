from contextlib import closing
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from addon.app.settings import get_db_path
from intentguard_core.models import (
    EntityCatalog,
    EntityClassification,
    EntityPermissions,
)

CREATE_ENTITY_CLASSIFICATIONS_TABLE = """
CREATE TABLE IF NOT EXISTS entity_classifications (
    entity_id TEXT PRIMARY KEY,
    real_world_name TEXT NOT NULL,
    category TEXT NOT NULL,
    impact TEXT NOT NULL,
    permissions_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


def get_database_path() -> Path:
    return get_db_path()


def ensure_database(db_path: str | Path | None = None) -> Path:
    database_path = Path(db_path) if db_path is not None else get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(CREATE_ENTITY_CLASSIFICATIONS_TABLE)
        _ensure_entity_classifications_schema(connection)
        connection.commit()

    return database_path


def upsert_entity_classification(
    classification: EntityClassification,
    db_path: str | Path | None = None,
) -> EntityClassification:
    database_path = ensure_database(db_path)
    timestamp = _utc_now()

    with closing(_connect(database_path)) as connection:
        with connection:
            existing_row = connection.execute(
                """
                SELECT created_at
                FROM entity_classifications
                WHERE entity_id = ?
                """,
                (classification.entity_id,),
            ).fetchone()
            created_at = existing_row["created_at"] if existing_row else timestamp
            if not created_at:
                created_at = timestamp

            connection.execute(
                """
                INSERT INTO entity_classifications (
                    entity_id,
                    real_world_name,
                    category,
                    impact,
                    permissions_json,
                    created_at,
                    updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(entity_id) DO UPDATE SET
                    real_world_name = excluded.real_world_name,
                    category = excluded.category,
                    impact = excluded.impact,
                    permissions_json = excluded.permissions_json,
                    created_at = excluded.created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    classification.entity_id,
                    classification.real_world_name,
                    classification.category,
                    classification.impact.value,
                    classification.permissions.model_dump_json(),
                    created_at,
                    timestamp,
                ),
            )

    return classification


def get_entity_classification(
    entity_id: str,
    db_path: str | Path | None = None,
) -> EntityClassification | None:
    database_path = ensure_database(db_path)

    with closing(_connect(database_path)) as connection:
        row = connection.execute(
            """
            SELECT
                entity_id,
                real_world_name,
                category,
                impact,
                permissions_json
            FROM entity_classifications
            WHERE entity_id = ?
            """,
            (entity_id,),
        ).fetchone()

    if row is None:
        return None

    return _row_to_entity_classification(row)


def list_entity_classifications(
    db_path: str | Path | None = None,
) -> list[EntityClassification]:
    database_path = ensure_database(db_path)

    with closing(_connect(database_path)) as connection:
        rows = connection.execute(
            """
            SELECT
                entity_id,
                real_world_name,
                category,
                impact,
                permissions_json
            FROM entity_classifications
            ORDER BY entity_id
            """
        ).fetchall()

    return [_row_to_entity_classification(row) for row in rows]


def build_entity_catalog_from_db(
    db_path: str | Path | None = None,
) -> EntityCatalog:
    return EntityCatalog(
        classifications=list_entity_classifications(db_path=db_path),
    )


def delete_entity_classification(
    entity_id: str,
    db_path: str | Path | None = None,
) -> bool:
    database_path = ensure_database(db_path)

    with closing(_connect(database_path)) as connection:
        with connection:
            cursor = connection.execute(
                """
                DELETE FROM entity_classifications
                WHERE entity_id = ?
                """,
                (entity_id,),
            )

    return cursor.rowcount > 0


def _connect(database_path: str | Path) -> sqlite3.Connection:
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    return connection


def _ensure_entity_classifications_schema(connection: sqlite3.Connection) -> None:
    existing_columns = {
        row[1]
        for row in connection.execute(
            "PRAGMA table_info(entity_classifications)"
        ).fetchall()
    }

    if "created_at" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE entity_classifications
            ADD COLUMN created_at TEXT NOT NULL DEFAULT ''
            """
        )

    if "updated_at" not in existing_columns:
        connection.execute(
            """
            ALTER TABLE entity_classifications
            ADD COLUMN updated_at TEXT NOT NULL DEFAULT ''
            """
        )


def _row_to_entity_classification(row: sqlite3.Row) -> EntityClassification:
    return EntityClassification(
        entity_id=row["entity_id"],
        real_world_name=row["real_world_name"],
        category=row["category"],
        impact=row["impact"],
        permissions=EntityPermissions.model_validate_json(row["permissions_json"]),
    )


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
