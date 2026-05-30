from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request, Response, status

from addon.app import ha_client
from addon.app.settings import get_db_path
from intentguard_core.matching import match_entity_candidates
from intentguard_core.models import (
    DesiredStatePolicySpec,
    EntityCandidate,
    EntityClassification,
    EntityMatchRequest,
    EntityCatalog,
    HomeAssistantSnapshot,
)
from intentguard_core.risk import assess_policy_risk
from intentguard_core.validation import validate_policy_spec

from addon.app.api_models import (
    DesiredStateValidationRequest,
    DesiredStateValidationResponse,
    ValidationResultResponse,
)
from addon.app.storage import (
    build_entity_catalog_from_db,
    delete_entity_classification,
    ensure_database,
    get_entity_classification,
    list_entity_classifications,
    upsert_entity_classification,
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.database_path = ensure_database(get_db_path())
    yield


app = FastAPI(
    title="IntentGuard",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ha/snapshot", response_model=HomeAssistantSnapshot)
async def read_homeassistant_snapshot() -> HomeAssistantSnapshot:
    return await _fetch_live_homeassistant_snapshot()


@app.get("/entities/candidates", response_model=list[EntityCandidate])
async def read_entity_candidates(
    request: Request,
    q: str = Query(min_length=1),
    domain: str | None = None,
    category: str | None = None,
    limit: int = Query(default=10, ge=1),
) -> list[EntityCandidate]:
    ha_snapshot = await _fetch_live_homeassistant_snapshot()
    catalog = build_entity_catalog_from_db(db_path=_database_path(request))
    match_request = EntityMatchRequest(
        query=q,
        requested_domain=domain,
        requested_category=category,
        limit=limit,
    )
    return match_entity_candidates(match_request, ha_snapshot, catalog)


@app.get("/entity-classifications", response_model=list[EntityClassification])
def read_entity_classifications(request: Request) -> list[EntityClassification]:
    return list_entity_classifications(db_path=_database_path(request))


@app.get(
    "/entity-classifications/{entity_id}",
    response_model=EntityClassification,
)
def read_entity_classification(
    entity_id: str, request: Request
) -> EntityClassification:
    classification = get_entity_classification(
        entity_id,
        db_path=_database_path(request),
    )
    if classification is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity classification '{entity_id}' was not found.",
        )
    return classification


@app.put(
    "/entity-classifications/{entity_id}",
    response_model=EntityClassification,
)
def put_entity_classification(
    entity_id: str,
    classification: EntityClassification,
    request: Request,
) -> EntityClassification:
    if classification.entity_id != entity_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="entity_id in path and body must match.",
        )

    return upsert_entity_classification(
        classification,
        db_path=_database_path(request),
    )


@app.delete(
    "/entity-classifications/{entity_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def remove_entity_classification(entity_id: str, request: Request) -> Response:
    deleted = delete_entity_classification(
        entity_id,
        db_path=_database_path(request),
    )
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Entity classification '{entity_id}' was not found.",
        )

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@app.post(
    "/policies/desired-state/validate",
    response_model=DesiredStateValidationResponse,
)
def validate_desired_state_policy(
    payload: DesiredStateValidationRequest,
    request: Request,
) -> DesiredStateValidationResponse:
    database_path = _database_path(request)
    catalog = build_entity_catalog_from_db(db_path=database_path)
    return _build_desired_state_validation_response(
        payload.policy,
        payload.ha_snapshot.to_core_model(),
        catalog,
    )


@app.post(
    "/policies/desired-state/validate-live",
    response_model=DesiredStateValidationResponse,
)
async def validate_desired_state_policy_live(
    policy: DesiredStatePolicySpec,
    request: Request,
) -> DesiredStateValidationResponse:
    ha_snapshot = await _fetch_live_homeassistant_snapshot()
    catalog = build_entity_catalog_from_db(db_path=_database_path(request))
    return _build_desired_state_validation_response(
        policy,
        ha_snapshot,
        catalog,
    )


def _build_desired_state_validation_response(
    policy: DesiredStatePolicySpec,
    ha_snapshot: HomeAssistantSnapshot,
    catalog: EntityCatalog,
) -> DesiredStateValidationResponse:
    validation = validate_policy_spec(
        policy,
        ha_snapshot=ha_snapshot,
        catalog=catalog,
    )
    classification = catalog.get_classification(policy.target_entity_id)
    risk = assess_policy_risk(policy, classification) if classification is not None else None
    deployable_in_principle = validation.is_valid and risk is not None and risk.auto_deploy_allowed

    return DesiredStateValidationResponse(
        valid=validation.is_valid,
        validation=ValidationResultResponse.from_core_result(validation),
        risk=risk,
        deployable_in_principle=deployable_in_principle,
    )


async def _fetch_live_homeassistant_snapshot() -> HomeAssistantSnapshot:
    try:
        return await ha_client.fetch_homeassistant_snapshot()
    except (
        ha_client.HomeAssistantConfigurationError,
        ha_client.HomeAssistantUnavailableError,
    ) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc


def _database_path(request: Request) -> Path:
    return Path(request.app.state.database_path)
