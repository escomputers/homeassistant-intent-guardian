"""Pure deterministic entity candidate matching for IntentGuard."""

from intentguard_core.models import (
    EntityCandidate,
    EntityCatalog,
    EntityClassification,
    EntityMatchRequest,
    HomeAssistantEntityState,
    HomeAssistantSnapshot,
    MatchConfidence,
)


def match_entity_candidates(
    request: EntityMatchRequest,
    ha_snapshot: HomeAssistantSnapshot,
    catalog: EntityCatalog,
) -> list[EntityCandidate]:
    """Rank entity candidates using only snapshot and catalog data."""
    candidates: list[EntityCandidate] = []
    for entity in ha_snapshot.entities:
        if not _matches_requested_domain(request.requested_domain, entity.domain):
            continue

        classification = catalog.get_classification(entity.entity_id)
        candidate = _score_entity(request, entity, classification)
        if candidate is not None:
            candidates.append(candidate)

    candidates.sort(key=lambda candidate: (-candidate.score, candidate.entity_id))
    return candidates[: request.limit]


def _score_entity(
    request: EntityMatchRequest,
    entity: HomeAssistantEntityState,
    classification: EntityClassification | None,
) -> EntityCandidate | None:
    query_text = _normalize_text(request.query)
    query_tokens = _tokenize(request.query)
    if not query_text:
        return None

    score = 0.0
    reasons: list[str] = []
    entity_id_text = _normalize_text(entity.entity_id)
    friendly_name_text = _normalize_text(entity.friendly_name)
    area_text = _normalize_text(entity.area)
    classification_name_text = _normalize_text(
        classification.real_world_name if classification is not None else None
    )

    if friendly_name_text and friendly_name_text == query_text:
        score += 0.7
        reasons.append("Exact friendly_name match.")
    elif friendly_name_text and query_text in friendly_name_text:
        score += 0.45
        reasons.append("Partial friendly_name match.")

    if entity_id_text == query_text:
        score += 0.65
        reasons.append("Exact entity_id match.")
    elif query_text in entity_id_text:
        score += 0.4
        reasons.append("Partial entity_id match.")

    if area_text and area_text == query_text:
        score += 0.2
        reasons.append("Exact area match.")
    elif area_text and query_text in area_text:
        score += 0.1
        reasons.append("Partial area match.")

    if classification_name_text and classification_name_text == query_text:
        score += 0.35
        reasons.append("Exact classified real_world_name match.")
    elif classification_name_text and query_text in classification_name_text:
        score += 0.2
        reasons.append("Partial classified real_world_name match.")

    area_token_overlap = _area_token_overlap_score(query_tokens, entity.area)
    if area_token_overlap > 0:
        score += area_token_overlap
        reasons.append("Query token matches area.")

    metadata_token_overlap = _metadata_token_overlap_score(
        query_tokens,
        entity,
        classification,
    )
    if metadata_token_overlap > 0:
        score += metadata_token_overlap
        reasons.append("Query tokens overlap with entity metadata.")

    requested_category = _normalize_text(request.requested_category)
    classification_category = _normalize_text(
        classification.category if classification is not None else None
    )
    if requested_category:
        if classification_category == requested_category:
            score += 0.15
            reasons.append("Requested category matches stored classification.")
        elif classification is not None:
            score -= 0.15
            reasons.append("Requested category differs from stored classification.")

    if classification is not None and score > 0:
        score += 0.05
        reasons.append("Entity is already classified in the catalog.")

    normalized_score = round(max(0.0, min(score, 1.0)), 3)
    if normalized_score <= 0.0 and _has_requested_domain(request.requested_domain):
        normalized_score = 0.05
        reasons.append("Matches requested domain filter.")

    if normalized_score <= 0.0:
        return None

    return EntityCandidate(
        entity_id=entity.entity_id,
        domain=entity.domain,
        friendly_name=entity.friendly_name,
        area=entity.area,
        device_class=entity.device_class,
        score=normalized_score,
        confidence=_confidence_for_score(normalized_score),
        already_classified=classification is not None,
        existing_classification=classification,
        reasons=reasons,
    )


def _area_token_overlap_score(
    query_tokens: set[str],
    area: str | None,
) -> float:
    overlap_count = _token_overlap_count(query_tokens, area)
    return min(overlap_count * 0.08, 0.16)


def _metadata_token_overlap_score(
    query_tokens: set[str],
    entity: HomeAssistantEntityState,
    classification: EntityClassification | None,
) -> float:
    if not query_tokens:
        return 0.0

    candidate_tokens = set()
    candidate_tokens.update(_tokenize(entity.entity_id))
    candidate_tokens.update(_tokenize(entity.friendly_name))
    candidate_tokens.update(_tokenize(entity.device_class))
    if classification is not None:
        candidate_tokens.update(_tokenize(classification.real_world_name))
        candidate_tokens.update(_tokenize(classification.category))

    overlap_count = len(query_tokens & candidate_tokens)
    return min(overlap_count * 0.08, 0.24)


def _token_overlap_count(query_tokens: set[str], value: str | None) -> int:
    if not query_tokens:
        return 0

    return len(query_tokens & _tokenize(value))


def _normalize_text(value: str | None) -> str:
    if not value:
        return ""
    return (
        value.strip()
        .lower()
        .replace("_", " ")
        .replace(".", " ")
        .replace("-", " ")
    )


def _matches_requested_domain(
    requested_domain: str | None,
    entity_domain: str | None,
) -> bool:
    normalized_requested_domain = _normalize_text(requested_domain)
    if not normalized_requested_domain:
        return True

    return _normalize_text(entity_domain) == normalized_requested_domain


def _has_requested_domain(requested_domain: str | None) -> bool:
    return bool(_normalize_text(requested_domain))


def _tokenize(value: str | None) -> set[str]:
    normalized = _normalize_text(value)
    return {token for token in normalized.split() if token}


def _confidence_for_score(score: float) -> MatchConfidence:
    if score >= 0.7:
        return MatchConfidence.HIGH
    if score >= 0.4:
        return MatchConfidence.MEDIUM
    return MatchConfidence.LOW
