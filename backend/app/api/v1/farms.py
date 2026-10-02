import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from pydantic import BaseModel

from app.api.deps import DB, Ctx, Paging, read_upload, require_any
from app.repositories import farms as farm_repo
from app.schemas.common import IdRef, Page, Reason, validate_payload
from app.schemas.farms import (
    AmendIn,
    BoundaryIn,
    BoundaryOut,
    EvidenceIn,
    EvidenceOut,
    FarmCreate,
    FarmOut,
    FarmSummary,
    FarmTransition,
    FarmUpdate,
    GeometryIn,
    GeometryReportOut,
    HistoryOut,
    NearbyFarm,
    OverlapOut,
    OverlapResolve,
    OwnershipEnd,
    OwnershipIn,
    OwnershipOut,
    ReviewDecision,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import farm_history_service as history
from app.services import farm_service as svc
from app.services import gis_service
from app.services.farm_mappers import boundary_out, evidence_out, farm_out, farm_summaries, overlap_out, ownership_out

router = APIRouter(prefix="/farms", tags=["farms"])
Reader = Annotated[Principal, Depends(require_any(P.FARMS_READ, P.FARMERS_SELF))]
Manager = Annotated[Principal, Depends(require_any(P.FARMS_MANAGE, P.FARMERS_SELF))]
Reviewer = Annotated[Principal, Depends(require_any(P.FARMS_REVIEW))]
OverlapReviewer = Annotated[Principal, Depends(require_any(P.FARMS_REVIEW, P.FARMS_REVIEW_CROSS_ORG))]
Kind = Literal["land", "crop", "practice"]


class ReasonBody(BaseModel):
    reason: Reason


class BoundarySaved(BaseModel):
    farm: FarmOut
    warnings: list[str]


@router.get("", response_model=Page[FarmSummary])
def list_farms(principal: Reader, db: DB, paging: Paging, search: Annotated[str | None, Query(max_length=100)] = None,
               status_: Annotated[str | None, Query(alias="status", max_length=20)] = None, farmer_id: uuid.UUID | None = None,
               organization_id: uuid.UUID | None = None, environment: Literal["LIVE", "DEMO"] | None = None,
               has_open_overlaps: bool | None = None) -> Page[FarmSummary]:
    rows, total = svc.list_farms(db, principal, paging, search=search, status=status_, farmer_id=farmer_id,
                                 organization_id=organization_id, environment=environment, has_open_overlaps=has_open_overlaps)
    return Page(items=farm_summaries(db, rows), total=total, page=paging.page, page_size=paging.page_size)


@router.post("", response_model=FarmOut, status_code=status.HTTP_201_CREATED)
def create_farm(body: FarmCreate, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.create_farm(db, ctx, principal, body))


@router.post("/geometry/validate", response_model=GeometryReportOut,
             summary="Validate a boundary with SQL Server (area, validity, warnings) without saving it")
def validate_geometry(body: GeometryIn, principal: Reader, db: DB) -> GeometryReportOut:
    c = gis_service.check_boundary(db, gis_service.parse_input(body.geojson, body.kml))
    return GeometryReportOut(geojson=c.geojson, area_m2=c.area_m2, area_hectares=c.area_hectares, perimeter_m=c.perimeter_m,
                             centroid_lat=c.centroid_lat, centroid_lon=c.centroid_lon, vertex_count=c.vertex_count,
                             notes=c.notes, warnings=c.warnings)


@router.get("/spatial/near", response_model=list[NearbyFarm], summary="Farms within a radius of a point (STDistance)")
def near(principal: Reader, db: DB, lat: float, lon: float, radius_m: Annotated[float, Query(gt=0, le=50_000)],
         environment: Literal["LIVE", "DEMO"] = "LIVE") -> list[NearbyFarm]:
    return [NearbyFarm(farm_id=f.id, farm_code=f.farm_code, name=f.name, status=f.status, distance_m=d)
            for f, d in svc.farms_near(db, principal, lat, lon, radius_m, environment)]


@router.get("/spatial/at-point", response_model=list[FarmSummary], summary="Farms whose boundary contains a point")
def at_point(principal: Reader, db: DB, lat: float, lon: float, environment: Literal["LIVE", "DEMO"] = "LIVE") -> list[FarmSummary]:
    return farm_summaries(db, svc.farms_at_point(db, principal, lat, lon, environment))


@router.get("/{farm_id}", response_model=FarmOut)
def get_farm(farm_id: uuid.UUID, principal: Reader, db: DB) -> FarmOut:
    return farm_out(db, principal, svc.get_farm(db, principal, farm_id))


@router.patch("/{farm_id}", response_model=FarmOut)
def update_farm(farm_id: uuid.UUID, body: FarmUpdate, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.update_farm(db, ctx, principal, farm_id, body))


# ---------- boundary
@router.post("/{farm_id}/boundary", response_model=BoundarySaved, summary="Save a new boundary version (GeoJSON or KML text)")
def save_boundary(farm_id: uuid.UUID, body: BoundaryIn, principal: Manager, db: DB, ctx: Ctx) -> BoundarySaved:
    farm, warnings = svc.save_boundary(db, ctx, principal, farm_id, body.geojson, body.kml, body.source)
    return BoundarySaved(farm=farm_out(db, principal, farm), warnings=warnings)


@router.post("/{farm_id}/boundary/upload", response_model=BoundarySaved, summary="Upload a GeoJSON / KML boundary file")
def upload_boundary(farm_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()]) -> BoundarySaved:
    farm, warnings = svc.save_boundary_from_file(db, ctx, principal, farm_id, file.filename, read_upload(file))
    return BoundarySaved(farm=farm_out(db, principal, farm), warnings=warnings)


@router.get("/{farm_id}/boundaries", response_model=list[BoundaryOut], summary="All boundary versions, newest first")
def boundaries(farm_id: uuid.UUID, principal: Reader, db: DB) -> list[BoundaryOut]:
    svc.get_farm(db, principal, farm_id)
    return [boundary_out(b) for b in farm_repo.boundaries(db, farm_id)]


@router.get("/{farm_id}/overlaps", response_model=list[OverlapOut])
def overlaps(farm_id: uuid.UUID, principal: Reader, db: DB, include_obsolete: bool = False) -> list[OverlapOut]:
    farm = svc.get_farm(db, principal, farm_id)
    return [overlap_out(db, principal, farm, c) for c in farm_repo.overlaps(db, farm_id, include_closed=include_obsolete)]


@router.post("/{farm_id}/overlaps/{check_id}/resolve", response_model=OverlapOut)
def resolve_overlap(farm_id: uuid.UUID, check_id: uuid.UUID, body: OverlapResolve, principal: OverlapReviewer, db: DB, ctx: Ctx) -> OverlapOut:
    c = svc.resolve_overlap(db, ctx, principal, farm_id, check_id, body.resolution, body.notes)
    return overlap_out(db, principal, svc.get_farm(db, principal, farm_id), c)


# ---------- ownership
@router.get("/{farm_id}/ownership", response_model=list[OwnershipOut])
def list_ownership(farm_id: uuid.UUID, principal: Reader, db: DB) -> list[OwnershipOut]:
    svc.get_farm(db, principal, farm_id)
    return [ownership_out(o) for o in farm_repo.ownerships(db, farm_id)]


@router.post("/{farm_id}/ownership", response_model=OwnershipOut, status_code=status.HTTP_201_CREATED)
def add_ownership(farm_id: uuid.UUID, body: OwnershipIn, principal: Manager, db: DB, ctx: Ctx) -> OwnershipOut:
    return ownership_out(svc.add_ownership(db, ctx, principal, farm_id, body))


@router.post("/{farm_id}/ownership/{ownership_id}/end", response_model=OwnershipOut)
def end_ownership(farm_id: uuid.UUID, ownership_id: uuid.UUID, body: OwnershipEnd, principal: Manager, db: DB, ctx: Ctx) -> OwnershipOut:
    return ownership_out(svc.end_ownership(db, ctx, principal, farm_id, ownership_id, body.valid_to, body.reason))


@router.post("/{farm_id}/ownership/{ownership_id}/review", response_model=OwnershipOut)
def review_ownership(farm_id: uuid.UUID, ownership_id: uuid.UUID, body: ReviewDecision, principal: Reviewer, db: DB,
                     ctx: Ctx) -> OwnershipOut:
    return ownership_out(svc.review_ownership(db, ctx, principal, farm_id, ownership_id, body.status, body.notes))


# ---------- history
@router.get("/{farm_id}/history/{kind}", response_model=list[HistoryOut])
def list_history(farm_id: uuid.UUID, kind: Kind, principal: Reader, db: DB, include_retracted: bool = False) -> list[HistoryOut]:
    svc.get_farm(db, principal, farm_id)
    return history.list_history(db, farm_id, kind, include_retracted)


@router.post("/{farm_id}/history/{kind}", response_model=HistoryOut, status_code=status.HTTP_201_CREATED)
def add_history(farm_id: uuid.UUID, kind: Kind, body: dict[str, Any], principal: Manager, db: DB, ctx: Ctx) -> HistoryOut:
    from app.services.farm_history_service import KINDS
    data = validate_payload(KINDS[kind][1], body)
    return svc.history_action(db, ctx, principal, farm_id, kind, "add", data=data)  # type: ignore[no-any-return]


@router.get("/{farm_id}/history/{kind}/{record_id}/versions", response_model=list[HistoryOut])
def history_versions(farm_id: uuid.UUID, kind: Kind, record_id: uuid.UUID, principal: Reader, db: DB) -> list[HistoryOut]:
    svc.get_farm(db, principal, farm_id)
    return history.versions(db, farm_id, kind, record_id)


@router.post("/{farm_id}/history/{kind}/{record_id}/amend", response_model=HistoryOut, summary="New version; old version kept")
def amend_history(farm_id: uuid.UUID, kind: Kind, record_id: uuid.UUID, body: AmendIn, principal: Manager, db: DB, ctx: Ctx) -> HistoryOut:
    return svc.history_action(db, ctx, principal, farm_id, kind, "amend", record_id=record_id, changes=body.data,  # type: ignore[no-any-return]
                              reason=body.reason)


@router.post("/{farm_id}/history/{kind}/{record_id}/retract", response_model=HistoryOut)
def retract_history(farm_id: uuid.UUID, kind: Kind, record_id: uuid.UUID, body: ReasonBody, principal: Manager, db: DB,
                    ctx: Ctx) -> HistoryOut:
    return svc.history_action(db, ctx, principal, farm_id, kind, "retract", record_id=record_id, reason=body.reason)  # type: ignore[no-any-return]


@router.post("/{farm_id}/history/{kind}/{record_id}/review", response_model=HistoryOut)
def review_history(farm_id: uuid.UUID, kind: Kind, record_id: uuid.UUID, body: ReviewDecision, principal: Reviewer, db: DB,
                   ctx: Ctx) -> HistoryOut:
    return svc.history_action(db, ctx, principal, farm_id, kind, "review", record_id=record_id, reason=body.notes,  # type: ignore[no-any-return]
                              status=body.status)


# ---------- evidence & documents
@router.get("/{farm_id}/evidence", response_model=list[EvidenceOut])
def list_evidence(farm_id: uuid.UUID, principal: Reader, db: DB) -> list[EvidenceOut]:
    farm = svc.get_farm(db, principal, farm_id)
    return [evidence_out(db, farm, e) for e in farm_repo.evidence(db, farm_id)]


@router.post("/{farm_id}/evidence", response_model=EvidenceOut, status_code=status.HTTP_201_CREATED)
def add_evidence(farm_id: uuid.UUID, body: EvidenceIn, principal: Manager, db: DB, ctx: Ctx) -> EvidenceOut:
    e = svc.add_evidence(db, ctx, principal, farm_id, body)
    return evidence_out(db, svc.get_farm(db, principal, farm_id), e)


@router.post("/{farm_id}/evidence/{evidence_id}/review", response_model=EvidenceOut)
def review_evidence(farm_id: uuid.UUID, evidence_id: uuid.UUID, body: ReviewDecision, principal: Reviewer, db: DB,
                    ctx: Ctx) -> EvidenceOut:
    e = svc.review_evidence(db, ctx, principal, farm_id, evidence_id, body.status, body.notes)
    return evidence_out(db, svc.get_farm(db, principal, farm_id), e)


@router.post("/{farm_id}/documents", response_model=IdRef, status_code=status.HTTP_201_CREATED)
def upload_document(farm_id: uuid.UUID, principal: Manager, db: DB, ctx: Ctx, file: Annotated[UploadFile, File()],
                    category: Annotated[str, Form(max_length=30)], title: Annotated[str, Form(max_length=200)] = "") -> IdRef:
    return IdRef(id=svc.upload_document(db, ctx, principal, farm_id, category, title, file.filename, read_upload(file)))


# ---------- workflow
@router.post("/{farm_id}/submit", response_model=FarmOut)
def submit(farm_id: uuid.UUID, body: FarmTransition, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.submit(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/withdraw", response_model=FarmOut)
def withdraw(farm_id: uuid.UUID, body: FarmTransition, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.withdraw(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/start-review", response_model=FarmOut)
def start_review(farm_id: uuid.UUID, body: FarmTransition, principal: Reviewer, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.start_review(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/verify", response_model=FarmOut)
def verify(farm_id: uuid.UUID, body: FarmTransition, principal: Reviewer, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.verify(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/reject", response_model=FarmOut)
def reject(farm_id: uuid.UUID, body: FarmTransition, principal: Reviewer, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.reject(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/reopen", response_model=FarmOut)
def reopen(farm_id: uuid.UUID, body: FarmTransition, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.reopen(db, ctx, principal, farm_id, body.reason))


@router.post("/{farm_id}/inactivate", response_model=FarmOut)
def inactivate(farm_id: uuid.UUID, body: FarmTransition, principal: Manager, db: DB, ctx: Ctx) -> FarmOut:
    return farm_out(db, principal, svc.inactivate(db, ctx, principal, farm_id, body.reason))
