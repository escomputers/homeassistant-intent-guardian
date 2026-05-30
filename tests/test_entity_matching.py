from intentguard_core.matching import match_entity_candidates
from intentguard_core.models import (
    EntityCatalog,
    EntityClassification,
    EntityMatchRequest,
    MatchConfidence,
    EntityPermissions,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
    ImpactLevel,
)


def test_exact_friendly_name_match_ranks_first() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.luci_giardino",
            friendly_name="Luci giardino",
            domain="light",
            area="Esterno",
        ),
        HomeAssistantEntityState(
            entity_id="light.cucina",
            friendly_name="Luci cucina",
            domain="light",
            area="Cucina",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino"),
        snapshot,
        build_catalog(),
    )

    assert candidates[0].entity_id == "light.luci_giardino"
    assert "Exact friendly_name match." in candidates[0].reasons


def test_partial_entity_id_match_works() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="switch.shelly_garden_01",
            friendly_name="Shelly giardino",
            domain="switch",
        )
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="garden"),
        snapshot,
        build_catalog(),
    )

    assert candidates[0].entity_id == "switch.shelly_garden_01"
    assert candidates[0].score > 0


def test_requested_domain_returns_weak_matching_domain_candidate_with_low_confidence() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb",
            friendly_name="Tapo L530 smart bulb",
            domain="light",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino", requested_domain="light"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "light.tapo_l530_smart_bulb"
    ]
    assert candidates[0].confidence is MatchConfidence.LOW
    assert candidates[0].score == 0.05
    assert "Matches requested domain filter." in candidates[0].reasons


def test_area_match_improves_score_within_requested_domain() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb",
            friendly_name="Tapo L530 smart bulb",
            domain="light",
            area="Giardino",
        ),
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb_2",
            friendly_name="Tapo L530 smart bulb",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino", requested_domain="light"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "light.tapo_l530_smart_bulb",
        "light.tapo_l530_smart_bulb_2",
    ]
    assert candidates[0].score > candidates[1].score
    assert "Query token matches area." in candidates[0].reasons
    assert candidates[0].confidence is MatchConfidence.LOW


def test_requested_automation_domain_can_return_automation_entities() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb",
            friendly_name="Lampadina giardino",
            domain="light",
            area="Giardino",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino", requested_domain="automation"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "automation.luci_giardino_on_20_30_everyday"
    ]


def test_no_domain_filter_keeps_broad_matching_behavior() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb",
            friendly_name="Tapo L530 smart bulb",
            domain="light",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "automation.luci_giardino_on_20_30_everyday",
    ]


def test_exact_and_partial_matches_work_within_requested_domain() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.luci_giardino",
            friendly_name="Luci giardino",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="light.luci_giardino_secondarie",
            friendly_name="Luci secondarie",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino", requested_domain="light"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "light.luci_giardino",
        "light.luci_giardino_secondarie",
    ]


def test_stronger_match_within_requested_domain_ranks_above_weak_candidate() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.tapo_l530_smart_bulb",
            friendly_name="Tapo L530 smart bulb",
            domain="light",
            area="Giardino",
        ),
        HomeAssistantEntityState(
            entity_id="light.luci_giardino",
            friendly_name="Luci giardino",
            domain="light",
            area="Esterno",
        ),
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino", requested_domain="light"),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "light.luci_giardino",
        "light.tapo_l530_smart_bulb",
    ]
    assert candidates[0].score > candidates[1].score


def test_category_matching_uses_existing_classification() -> None:
    classification = EntityClassification(
        entity_id="switch.pompa_pozzo",
        real_world_name="Pompa pozzo",
        category="pump",
        impact=ImpactLevel.HIGH,
        permissions=EntityPermissions(turn_off=True),
    )
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="switch.pompa_pozzo",
            friendly_name="Shelly pozzo",
            domain="switch",
        ),
        HomeAssistantEntityState(
            entity_id="switch.altro",
            friendly_name="Altro switch",
            domain="switch",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="pozzo", requested_category="pump"),
        snapshot,
        build_catalog(classification),
    )

    assert candidates[0].entity_id == "switch.pompa_pozzo"
    assert candidates[0].already_classified is True
    assert candidates[0].existing_classification == classification


def test_candidates_are_sorted_by_score_descending() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.luci_giardino",
            friendly_name="Luci giardino",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="light.luci_giardino_secondarie",
            friendly_name="Luci secondarie",
            domain="light",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="Luci giardino"),
        snapshot,
        build_catalog(),
    )

    assert len(candidates) == 2
    assert candidates[0].score >= candidates[1].score


def test_no_match_returns_empty_list() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="sensor.freezer",
            friendly_name="Freezer",
            domain="sensor",
        )
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(query="garden lights"),
        snapshot,
        build_catalog(),
    )

    assert candidates == []


def test_limit_is_applied_after_filtering_and_sorting() -> None:
    snapshot = build_snapshot(
        HomeAssistantEntityState(
            entity_id="light.luci_giardino",
            friendly_name="Luci giardino",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="light.luci_giardino_secondarie",
            friendly_name="Luci secondarie",
            domain="light",
        ),
        HomeAssistantEntityState(
            entity_id="automation.luci_giardino_on_20_30_everyday",
            friendly_name="Luci giardino",
            domain="automation",
        ),
    )

    candidates = match_entity_candidates(
        EntityMatchRequest(
            query="Luci giardino",
            requested_domain="light",
            limit=1,
        ),
        snapshot,
        build_catalog(),
    )

    assert [candidate.entity_id for candidate in candidates] == [
        "light.luci_giardino"
    ]


def build_snapshot(*entities: HomeAssistantEntityState) -> HomeAssistantSnapshot:
    return HomeAssistantSnapshot(entities=list(entities))


def build_catalog(*classifications: EntityClassification) -> EntityCatalog:
    return EntityCatalog(classifications=list(classifications))
