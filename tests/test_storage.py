import sqlite3

from addon.app.storage import (
    delete_entity_classification,
    get_entity_classification,
    list_entity_classifications,
    upsert_entity_classification,
)
from intentguard_core.models import (
    EntityClassification,
    EntityPermissions,
    ImpactLevel,
)


def test_storage_round_trip_for_entity_classification(tmp_path) -> None:
    db_path = tmp_path / "intentguard.db"
    classification = build_classification()

    saved = upsert_entity_classification(classification, db_path=db_path)
    loaded = get_entity_classification(classification.entity_id, db_path=db_path)
    all_classifications = list_entity_classifications(db_path=db_path)

    assert saved == classification
    assert loaded == classification
    assert all_classifications == [classification]


def test_storage_update_and_delete_entity_classification(tmp_path) -> None:
    db_path = tmp_path / "intentguard.db"
    original = build_classification()
    updated = original.model_copy(update={"real_world_name": "Updated garden lights"})

    upsert_entity_classification(original, db_path=db_path)
    upsert_entity_classification(updated, db_path=db_path)

    assert get_entity_classification(original.entity_id, db_path=db_path) == updated
    assert delete_entity_classification(original.entity_id, db_path=db_path) is True
    assert get_entity_classification(original.entity_id, db_path=db_path) is None
    assert delete_entity_classification(original.entity_id, db_path=db_path) is False


def test_storage_creates_timestamp_columns(tmp_path) -> None:
    db_path = tmp_path / "intentguard.db"
    classification = build_classification()

    upsert_entity_classification(classification, db_path=db_path)

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1]
            for row in connection.execute(
                "PRAGMA table_info(entity_classifications)"
            ).fetchall()
        }

    assert "created_at" in columns
    assert "updated_at" in columns


def build_classification() -> EntityClassification:
    return EntityClassification(
        entity_id="light.garden_lights",
        real_world_name="Garden lights",
        category="light",
        impact=ImpactLevel.LOW,
        permissions=EntityPermissions(turn_on=True, turn_off=True, auto_modify=True),
    )
