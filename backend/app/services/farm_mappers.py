"""ORM → response mapping for farmers and farms (masking happens here, never in the client)."""
import uuid

from sqlalchemy.orm import Session

from app.models import Farm, FarmBoundary, Farmer, FarmerConsent, FarmEvidence, FarmOverlapCheck, FarmOwnership
from app.repositories import farmers as farmer_repo
from app.repositories import farms as farm_repo
from app.schemas.documents import document_out
from app.schemas.farmers import (
    AgreementOut,
    BankAccountOut,
    ConsentOut,
    ContactOut,
    FarmerOut,
    FarmerSummary,
    KycOut,
)
from app.schemas.farms import BoundaryOut, EvidenceOut, FarmOut, FarmSummary, OverlapOut, OwnershipOut
from app.security.principal import Principal
from app.services import consent_service, document_service, farm_history_service, farm_service, farmer_service
from app.services.workflows import FARM_MACHINE, FARMER_MACHINE


def _mask(last4: str | None) -> str | None:
    return f"••••{last4}" if last4 else None


def farmer_summaries(db: Session, farmers: list[Farmer]) -> list[FarmerSummary]:
    counts = farmer_repo.farm_counts(db, [f.id for f in farmers])
    names = farmer_repo.org_names(db, {f.organization_id for f in farmers})
    return [FarmerSummary(id=f.id, farmer_code=f.farmer_code, full_name=f.full_name, village=f.village, district=f.district,
                          state=f.state, country=f.country, status=f.status, organization_id=f.organization_id,
                          organization_name=names.get(f.organization_id), environment=f.environment,
                          farm_count=counts.get(f.id, 0), created_at=f.created_at) for f in farmers]


def consent_out(c: FarmerConsent, active: dict[str, uuid.UUID]) -> ConsentOut:
    d = c.definition
    return ConsentOut.model_validate({**{k: getattr(c, k) for k in ConsentOut.model_fields if hasattr(c, k)},
                                      "version": d.version if d else None, "required_for_activation": bool(d and d.required_for_activation),
                                      "is_current_version": bool(c.consent_definition_id) and active.get(c.consent_type) == c.consent_definition_id,
                                      "granted": c.status == "GRANTED", "granted_at": c.captured_at})


def farmer_out(db: Session, principal: Principal, f: Farmer) -> FarmerOut:
    active = {d.consent_type: d.id for d in consent_service.list_definitions(db)}
    base = farmer_summaries(db, [f])[0]
    cap = farmer_service.capabilities(principal, f)
    transitions = sorted(t for t in FARMER_MACHINE.allowed_from(f.status) if t not in ("KYC_PENDING", "KYC_VERIFIED")
                         and not (t == "REGISTERED" and f.status == "KYC_PENDING"))
    return FarmerOut(
        **base.model_dump(), group_organization_id=f.group_organization_id, user_id=f.user_id, gender=f.gender,
        date_of_birth=f.date_of_birth, preferred_language=f.preferred_language, participation_type=f.participation_type,
        address_line=f.address_line, sub_district=f.sub_district, postal_code=f.postal_code, updated_at=f.updated_at,
        kyc=KycOut(id_type=f.kyc_id_type, id_number_masked=_mask(f.kyc_id_last4), document_id=f.kyc_document_id,
                   possible_duplicate=f.kyc_possible_duplicate, submitted_at=f.kyc_submitted_at, submitted_by=f.kyc_submitted_by,
                   verified_at=f.kyc_verified_at, verified_by=f.kyc_verified_by, notes=f.kyc_notes),
        contacts=[ContactOut.model_validate(c, from_attributes=True) for c in f.contacts],
        consents=[consent_out(c, active) for c in f.consents],
        agreements=[AgreementOut.model_validate(a, from_attributes=True) for a in f.agreements],
        bank_accounts=[BankAccountOut(id=b.id, account_holder_name=b.account_holder_name, bank_name=b.bank_name,
                                      branch_name=b.branch_name, routing_code=b.routing_code,
                                      account_number_masked=_mask(b.account_last4) or "", is_primary=b.is_primary, status=b.status,
                                      proof_document_id=b.proof_document_id, verified_at=b.verified_at, review_notes=b.review_notes,
                                      created_at=b.created_at) for b in f.bank_accounts],
        documents=[document_out(d) for d in document_service.list_for(db, "farmer", f.id)],
        allowed_transitions=transitions, readiness=[r for r in farmer_service.readiness(db, f) if r.target in transitions],
        can_manage=cap.can_manage, can_verify_kyc=cap.can_verify_kyc, can_manage_bank=cap.can_manage_bank,
        can_verify_bank=cap.can_verify_bank, is_self=cap.is_self,
    )


def boundary_out(b: FarmBoundary) -> BoundaryOut:
    return BoundaryOut(id=b.id, version=b.version, status=b.status, source=b.source, source_document_id=b.source_document_id,
                       geojson=farm_service.boundary_out_geojson(b), area_hectares=b.area_hectares, area_m2=b.area_m2,
                       perimeter_m=b.perimeter_m, centroid_lat=b.centroid_lat, centroid_lon=b.centroid_lon,
                       vertex_count=b.vertex_count, validation_notes=b.validation_notes, created_by=b.created_by,
                       created_at=b.created_at, superseded_at=b.superseded_at)


def farm_summaries(db: Session, farms: list[Farm]) -> list[FarmSummary]:
    farmers = {f.id: f for f in (db.get(Farmer, fid) for fid in {x.farmer_id for x in farms}) if f}
    overlaps = farm_repo.open_overlap_counts(db, [f.id for f in farms])
    out = []
    for f in farms:
        b = db.get(FarmBoundary, f.current_boundary_id) if f.current_boundary_id else None
        fr = farmers.get(f.farmer_id)
        out.append(FarmSummary(id=f.id, farm_code=f.farm_code, name=f.name, farmer_id=f.farmer_id,
                               farmer_code=fr.farmer_code if fr else "", farmer_name=fr.full_name if fr else "",
                               organization_id=f.organization_id, village=f.village, district=f.district, state=f.state,
                               country=f.country, land_tenure=f.land_tenure, declared_area_hectares=f.declared_area_hectares,
                               area_hectares=f.area_hectares, status=f.status, open_overlaps=overlaps.get(f.id, 0),
                               environment=f.environment, centroid_lat=b.centroid_lat if b else None,
                               centroid_lon=b.centroid_lon if b else None, created_at=f.created_at))
    return out


def farm_out(db: Session, principal: Principal, f: Farm) -> FarmOut:
    from app.security.permissions import P
    from app.services import access
    base = farm_summaries(db, [f])[0]
    owner = farm_repo.owner_user(db, f.farmer_id)
    b = farm_repo.current_boundary(db, f.id)
    transitions = sorted(FARM_MACHINE.allowed_from(f.status))
    return FarmOut(**base.model_dump(), sub_district=f.sub_district, current_boundary=boundary_out(b) if b else None,
                   submitted_at=f.submitted_at, submitted_by=f.submitted_by, reviewed_by=f.reviewed_by, verified_at=f.verified_at,
                   verified_by=f.verified_by, review_notes=f.review_notes, updated_at=f.updated_at, allowed_transitions=transitions,
                   readiness=farm_service.readiness(db, f), history_counts=farm_history_service.counts(db, f.id),
                   evidence_count=farm_repo.count(db, FarmEvidence, f.id), ownership_count=farm_repo.count(db, FarmOwnership, f.id),
                   can_manage=access.can(principal, P.FARMS_MANAGE, f.organization_id, owner),
                   can_review=principal.can_in_org(P.FARMS_REVIEW, f.organization_id), is_self=access.is_self(principal, owner),
                   documents=[document_out(d) for d in document_service.list_for(db, "farm", f.id)])


def ownership_out(o: FarmOwnership) -> OwnershipOut:
    return OwnershipOut.model_validate({**{c: getattr(o, c) for c in OwnershipOut.model_fields if c != "is_current"},
                                        "is_current": farm_service.ownership_is_current(o)})


def evidence_out(db: Session, farm: Farm, e: FarmEvidence) -> EvidenceOut:
    return EvidenceOut.model_validate({**{c: getattr(e, c) for c in EvidenceOut.model_fields if c != "distance_to_boundary_m"},
                                       "distance_to_boundary_m": farm_service.evidence_distance(db, farm, e)})


def overlap_out(db: Session, principal: Principal, farm: Farm, c: FarmOverlapCheck) -> OverlapOut:
    """Always present the check from `farm`'s point of view; hide the other farm if the caller cannot see it."""
    mine = c.farm_id == farm.id
    other_id = c.other_farm_id if mine else c.farm_id
    other_boundary_id = c.other_boundary_id if mine else c.boundary_id
    other = farm_repo.get(db, other_id)
    visible = bool(other and farm_service.can_see(db, principal, other))
    ob = db.get(FarmBoundary, other_boundary_id) if visible else None
    perms = farm_service.overlap_permissions(db, principal, farm, c) if c.status == "OPEN" else (False, False)
    return OverlapOut(id=c.id, farm_id=farm.id, boundary_id=c.boundary_id if mine else c.other_boundary_id,
                      other_farm_id=other_id if visible else None, other_farm_code=other.farm_code if visible and other else None,
                      other_farm_visible=visible, relation=c.relation if mine else {"CONTAINS": "WITHIN", "WITHIN": "CONTAINS"}.get(
                          c.relation, c.relation), overlap_area_m2=c.overlap_area_m2,
                      overlap_pct_of_farm=c.overlap_pct_of_farm if mine else c.overlap_pct_of_other,
                      overlap_pct_of_other=c.overlap_pct_of_other if mine else c.overlap_pct_of_farm, same_farmer=c.same_farmer,
                      same_organization=c.same_organization, status=c.status, detected_at=c.detected_at, resolved_by=c.resolved_by,
                      resolved_at=c.resolved_at, resolution_notes=c.resolution_notes,
                      other_geojson=farm_service.boundary_out_geojson(ob) if ob else None,
                      can_confirm=perms[0], can_clear=perms[1])
