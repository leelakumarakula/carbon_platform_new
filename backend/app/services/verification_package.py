"""Phase 8B — what a VVB may see of a submitted package (C9, C10, C11): an explicit allow-list, never a generic project read.

Allowed: project code / name, the reporting period, the submitted manifest as-is (incl. the Phase 8A internal finding summaries, C11),
methodology reference + its documents, calculation inputs / outputs / report, the dataset's sampling points and field collections,
farm code / area / boundary and farmer code of the sampled farms, the approved laboratory results used, MRV evidence (field photos …)
referenced by the manifest, and documents attached to the submission (VVB report, project evidence).
Never: KYC / government ID, bank or payout data, agreements, consent forms, land titles, unrelated projects / periods / farms, the
audit trail or any internal user list.
"""
import json
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.context import RequestContext
from app.core.errors import NotFound
from app.models import (
    CalculationInput,
    CalculationOutput,
    CalculationReadinessReview,
    CalculationReport,
    Document,
    Farm,
    FarmBoundary,
    Farmer,
    LabResult,
    MethodologyDocument,
    MethodologyVersion,
    MonitoringPeriod,
    MrvDataset,
    MrvEvidence,
    StratumFarm,
    VerificationAssignment,
    VerificationSubmission,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory, DocumentVersion
from app.services import document_service
from app.services import verification_access as va

SUBMISSION_ENTITY = "verification_submission"
# defence in depth: even if a manifest ever referenced one of these, a VVB never receives it (C10)
DENIED_CATEGORIES = frozenset({DocumentCategory.KYC_ID.value, DocumentCategory.BANK_PROOF.value, DocumentCategory.AGREEMENT.value,
                               DocumentCategory.LEASE_AGREEMENT.value, DocumentCategory.CONSENT_FORM.value, DocumentCategory.CARBON_RIGHTS.value,
                               DocumentCategory.LAND_TITLE.value, DocumentCategory.LAND_RECORD.value})
REF_REQUIRED = ("INPUT", "OUTPUT", "LAB_RESULT", "MRV_EVIDENCE", "DOCUMENT")


def manifest_of(db: Session, s: VerificationSubmission) -> dict[str, Any]:
    r = db.get(CalculationReadinessReview, s.readiness_review_id)
    return json.loads(r.manifest) if r is not None and r.manifest else {}


def _uuids(values: list[Any]) -> list[uuid.UUID]:
    out = []
    for v in values:
        try:
            out.append(uuid.UUID(str(v)))
        except (TypeError, ValueError):
            continue
    return out


def allowed_documents(db: Session, s: VerificationSubmission) -> dict[uuid.UUID, str]:
    """document id → why the VVB may read it (manifest-referenced or attached to the submission)."""
    m = manifest_of(db, s)
    found: dict[uuid.UUID, str] = {}
    rep = db.get(CalculationReport, s.calculation_report_id)
    if rep is not None:
        found[rep.document_id] = "CALCULATION_REPORT"
    meth = m.get("methodology") or {}
    vid = _uuids([meth.get("version_id")])
    mid = _uuids([meth.get("methodology_id")])
    if vid:
        mv = db.get(MethodologyVersion, vid[0])
        if mv is not None and mv.source_document_id:
            found[mv.source_document_id] = "METHODOLOGY"
    if mid:
        for md in db.scalars(select(MethodologyDocument).where(MethodologyDocument.methodology_id == mid[0])).all():
            if md.methodology_version_id is None or (vid and md.methodology_version_id == vid[0]):
                found[md.document_id] = "METHODOLOGY"
    lab_ids = _uuids([r.get("result_id") for r in m.get("laboratory_results", [])])
    if lab_ids:
        for lr in db.scalars(select(LabResult).where(LabResult.id.in_(lab_ids))).all():
            if lr.report_document_id:
                found[lr.report_document_id] = "LAB_REPORT"
    ev_ids = _uuids([e.get("id") for e in m.get("mrv_evidence", [])])
    if ev_ids:
        for e in db.scalars(select(MrvEvidence).where(MrvEvidence.id.in_(ev_ids), MrvEvidence.project_id == s.project_id)).all():
            if e.document_id:
                found[e.document_id] = "MRV_EVIDENCE"
    for d in document_service.list_for(db, SUBMISSION_ENTITY, s.id):
        found[d.id] = "SUBMISSION"
    if not found:
        return {}
    docs = {d.id: d for d in db.scalars(select(Document).where(Document.id.in_(list(found)))).all()}
    return {i: why for i, why in found.items()
            if i in docs and docs[i].category not in DENIED_CATEGORIES and docs[i].sensitivity != "RESTRICTED"
            and docs[i].environment == s.environment}


def document_refs(db: Session, s: VerificationSubmission) -> list[dict[str, Any]]:
    allowed = allowed_documents(db, s)
    if not allowed:
        return []
    docs = db.scalars(select(Document).where(Document.id.in_(list(allowed))).options(selectinload(Document.versions))
                      .order_by(Document.created_at)).all()
    out = []
    for d in docs:
        v = next((x for x in d.versions if x.version == d.current_version), None)
        out.append({"document_id": d.id, "source": allowed[d.id], "category": d.category, "title": d.title, "status": d.status,
                    "file_name": v.file_name if v else None, "mime_type": v.mime_type if v else None,
                    "size_bytes": v.size_bytes if v else None, "sha256": v.checksum_sha256 if v else None,
                    "uploaded_at": v.uploaded_at if v else None})
    return out


def download(db: Session, ctx: RequestContext, s: VerificationSubmission, a: VerificationAssignment, p: Any, principal: Any,
             document_id: uuid.UUID) -> tuple[DocumentVersion, bytes]:
    """Manifest-scoped VVB download: allow-list check → integrity re-hash → VVB_DOCUMENT_DOWNLOADED in both organizations."""
    if document_id not in allowed_documents(db, s):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    doc = db.scalars(select(Document).where(Document.id == document_id).options(selectinload(Document.versions))).first()
    if doc is None:
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    v, data = document_service.read_verified(db, ctx, doc)
    va.audit(db, ctx, principal, "VVB_DOCUMENT_DOWNLOADED", SUBMISSION_ENTITY, s.id, a, p,
             {"document_id": doc.id, "version": v.version, "category": doc.category, "sha256": v.checksum_sha256,
              "submission_code": s.submission_code, "downloaded_at": utcnow().isoformat() + "Z"}, None, "VVB")
    db.commit()
    return v, data


def _farms(db: Session, ds_snap: dict[str, Any]) -> list[dict[str, Any]]:
    pairs = {(x.get("stratum_id"), x.get("farm_id")) for x in ds_snap.get("sampling_points", [])}
    out: dict[str, dict[str, Any]] = {}
    for stratum_id, farm_id in sorted(p for p in pairs if p[0] and p[1]):
        sf = db.scalars(select(StratumFarm).where(StratumFarm.stratum_id == uuid.UUID(stratum_id), StratumFarm.farm_id == uuid.UUID(farm_id))).first()
        farm = db.get(Farm, uuid.UUID(farm_id))
        if farm is None or farm_id in out:
            continue
        b = db.get(FarmBoundary, sf.farm_boundary_id) if sf else None
        farmer = db.get(Farmer, farm.farmer_id)
        from app.services.farm_service import boundary_out_geojson
        out[farm_id] = {"farm_id": farm.id, "farm_code": farm.farm_code, "farmer_code": farmer.farmer_code if farmer else None,
                        "area_hectares": str(b.area_hectares) if b else (str(farm.area_hectares) if farm.area_hectares is not None else None),
                        "boundary_version": b.version if b else None, "boundary": boundary_out_geojson(b) if b else None}
    return list(out.values())


def package(db: Session, s: VerificationSubmission, a: VerificationAssignment, p: Any) -> dict[str, Any]:
    m = manifest_of(db, s)
    mp = db.get(MonitoringPeriod, s.monitoring_period_id)
    ds_ref = m.get("dataset") or {}
    ds_id = _uuids([ds_ref.get("id")])
    ds = db.get(MrvDataset, ds_id[0]) if ds_id else None
    ds_snap = json.loads(ds.snapshot) if ds is not None and ds.snapshot else {}
    inputs = db.scalars(select(CalculationInput).where(CalculationInput.run_id == s.calculation_run_id).order_by(CalculationInput.seq)).all()
    outputs = db.scalars(select(CalculationOutput).where(CalculationOutput.run_id == s.calculation_run_id).order_by(CalculationOutput.seq)).all()
    lab_ids = _uuids([r.get("result_id") for r in m.get("laboratory_results", [])])
    labs = db.scalars(select(LabResult).where(LabResult.id.in_(lab_ids))).all() if lab_ids else []
    sample_of = {str(r.get("result_id")): r.get("sample") for r in m.get("laboratory_results", [])}
    rep = db.get(CalculationReport, s.calculation_report_id)
    meth = m.get("methodology") or {}
    return {
        "label": "Calculated tCO2e — not verified, not issued",
        "project": {"code": p.project_code, "name": p.name, "environment": p.environment},
        "period": {"id": mp.id, "number": mp.period_number, "start_date": mp.start_date, "end_date": mp.end_date} if mp else None,
        "manifest": m, "manifest_sha256": s.manifest_sha256,
        "methodology": {k: meth.get(k) for k in ("code", "version_label", "is_demo_illustrative", "calculation_rules_version")},
        "calculation": {
            "run": m.get("calculation_run"),
            "inputs": [{"id": i.id, "seq": i.seq, "variable_code": i.variable_code, "source_type": i.source_type, "source_id": i.source_id,
                        "source_version": i.source_version, "source_code": i.source_code, "value": i.value, "value_kind": i.value_kind,
                        "unit": i.unit, "level": i.level, "farm_id": i.farm_id, "sampling_point_id": i.sampling_point_id} for i in inputs],
            "outputs": [{"id": o.id, "seq": o.seq, "step": o.step, "output_code": o.output_code, "rule_code": o.rule_code,
                         "equation_reference": o.equation_reference, "value": o.value, "unit": o.unit, "level": o.level,
                         "entity_id": o.entity_id, "input_refs": json.loads(o.input_refs or "{}"), "is_final": o.is_final} for o in outputs],
        },
        "report": {"id": rep.id, "report_code": rep.report_code, "version": rep.version, "content_sha256": rep.content_sha256,
                   "pdf_sha256": rep.pdf_sha256, "document_id": rep.document_id} if rep else None,
        "dataset": {"ref": ds_ref, "sampling_points": ds_snap.get("sampling_points", []), "field_collections": ds_snap.get("field_collections", []),
                    "strata": ds_snap.get("strata", [])},
        "farms": _farms(db, ds_snap),
        "laboratory_results": [{"result_id": r.id, "version": r.version, "sample": sample_of.get(str(r.id)), "result_type": r.result_type,
                                "value_number": str(r.value_number) if r.value_number is not None else None, "value_text": r.value_text,
                                "unit": r.unit, "method_reported": r.method_reported, "analysed_at": r.analysed_at, "status": r.status,
                                "report_document_id": r.report_document_id} for r in labs],
        "documents": document_refs(db, s),
    }


def target_ok(db: Session, s: VerificationSubmission, target_type: str, ref: str | None) -> bool:
    """A VVB finding may only point at something inside the submitted package."""
    if target_type in REF_REQUIRED and not ref:
        return False
    if not ref:
        return True
    r = ref.strip().lower()
    m = manifest_of(db, s)
    if target_type == "SUBMISSION":
        return r in (str(s.id), s.submission_code.lower())
    if target_type == "MONITORING_PERIOD":
        return r == str(s.monitoring_period_id)
    if target_type == "CALCULATION_RUN":
        return r == str(s.calculation_run_id)
    if target_type == "CALCULATION_REPORT":
        return r == str(s.calculation_report_id)
    if target_type == "DATASET":
        return r == str((m.get("dataset") or {}).get("id", "")).lower()
    if target_type == "METHODOLOGY":
        return r == str((m.get("methodology") or {}).get("version_id", "")).lower()
    if target_type == "LAB_RESULT":
        return r in {str(x.get("result_id", "")).lower() for x in m.get("laboratory_results", [])}
    if target_type == "MRV_EVIDENCE":
        return r in {str(x.get("id", "")).lower() for x in m.get("mrv_evidence", [])}
    if target_type == "DOCUMENT":
        return r in {str(i) for i in allowed_documents(db, s)}
    if target_type == "INPUT":
        ins = db.scalars(select(CalculationInput).where(CalculationInput.run_id == s.calculation_run_id)).all()
        return r in {str(x.id) for x in ins} | {str(x.seq) for x in ins}
    if target_type == "OUTPUT":
        outs = db.scalars(select(CalculationOutput).where(CalculationOutput.run_id == s.calculation_run_id)).all()
        return r in {str(x.id) for x in outs} | {str(x.seq) for x in outs}
    return False
