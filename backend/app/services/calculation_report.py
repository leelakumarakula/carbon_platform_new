"""Official calculation report of an APPROVED run (Phase 8A decisions B7, B8, B11).

Content is built only from frozen / immutable records: the run's frozen input snapshot (methodology lock, module declaration,
inputs with sources), its append-only outputs, its completed QA reviews, its findings and the APPROVED dataset's frozen snapshot.
No live source table (laboratory results, monitoring records, strata, farms, users) is read. Content is canonical JSON with a
SHA-256; the PDF is a deterministic text rendering of that content (no timestamps or random IDs), so re-rendering the stored content
gives byte-identical output. A report is immutable; a new version supersedes it only when the deterministic content (for example the
findings) or the generator version differs.
"""
import hashlib
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record
from app.calculation import framework as fw
from app.core.config import get_settings
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound
from app.integrations.storage import get_storage
from app.models import (
    CalculationFinding,
    CalculationReport,
    CalculationRun,
    Document,
    DocumentVersion,
    MrvDataset,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.reports import pdf
from app.repositories.sequences import next_code
from app.schemas.calculation import CALCULATED_LABEL, DEMO_LABEL
from app.security.permissions import P
from app.security.principal import Principal
from app.services import calculation_service as cs
from app.services import document_service

GENERATOR_VERSION = f"calc-report-1.0+{pdf.WRITER_VERSION}"
ENTITY = "calculation_run"


def _document_resolver(db: Session, principal: Principal, run_id: uuid.UUID, kind: str) -> None:
    """Documents attached to a calculation run (reports, finding evidence) follow the run's calculation permissions."""
    run = db.get(CalculationRun, run_id)
    nf = NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")
    if run is None:
        raise nf
    try:
        cs.project_for(db, principal, run.project_id, *((P.CALCULATION_MANAGE, P.CALCULATION_REVIEW) if kind == "manage" else
                                                        (P.CALCULATION_READ,)))
    except NotFound:
        raise nf from None


document_service.register_resolver(ENTITY, _document_resolver)


def current_report(db: Session, run_id: uuid.UUID) -> CalculationReport | None:
    return db.scalars(select(CalculationReport).where(CalculationReport.run_id == run_id, CalculationReport.status == "CURRENT")).first()


def reports_of(db: Session, run_id: uuid.UUID) -> list[CalculationReport]:
    return list(db.scalars(select(CalculationReport).where(CalculationReport.run_id == run_id).order_by(CalculationReport.version)).all())


def _ds_snapshot(db: Session, run: CalculationRun) -> dict[str, Any]:
    ds = db.get(MrvDataset, run.mrv_dataset_id) if run.mrv_dataset_id else None
    return json.loads(ds.snapshot) if ds and ds.snapshot else {}


def build_content(db: Session, run: CalculationRun) -> dict[str, Any]:
    """Deterministic report content (canonical-JSON-ready) from frozen records only."""
    snap = json.loads(run.input_snapshot or "{}")
    ds = _ds_snapshot(db, run)
    points = {x["id"]: x for x in ds.get("sampling_points", [])}
    collections = {x["id"]: x for x in ds.get("field_collections", [])}
    strata = {x["id"]: x for x in ds.get("strata", [])}
    mod = snap.get("module", {})
    inputs = []
    for r in snap.get("inputs", []):
        fc = collections.get(r.get("field_collection_id") or "")
        pt, st = points.get(r.get("sampling_point_id") or ""), strata.get(r.get("stratum_id") or "")
        inputs.append({k: r.get(k) for k in ("seq", "variable", "source_type", "source_id", "source_version", "source_code", "value", "unit", "level",
                                              "requirement_source", "source_reference", "source_sha256", "farm_id")}
                      | {"field_collection": f"{fc['code']} v{fc['version']}" if fc else None, "sampling_point": pt["code"] if pt else None,
                         "stratum": f"{st['code']} v{st['version']}" if st else None})
    reviews = [{"id": str(rv.id), "result": rv.result, "completed_by": str(rv.completed_by), "completed_at": rv.completed_at.isoformat() + "Z",
                "notes": rv.notes, "checks": {c["key"]: c["result"] for c in json.loads(rv.checks or "[]")}}
               for rv in cs.qa_reviews(db, run.id) if rv.completed_at is not None]
    findings = [{"code": f.finding_code, "category": f.category, "blocking": f.blocking, "status": f.status, "title": f.title,
                 "target": {"input_seq": f.target_input_seq, "output_seq": f.target_output_seq,
                            "calculation_rule_id": str(f.target_calculation_rule_id) if f.target_calculation_rule_id else None,
                            "source_type": f.target_source_type, "source_id": str(f.target_source_id) if f.target_source_id else None}}
                for f in db.scalars(select(CalculationFinding).where(CalculationFinding.run_id == run.id)
                                    .order_by(CalculationFinding.finding_code)).all()]
    labels = [CALCULATED_LABEL]
    if run.environment == "DEMO" or snap.get("methodology", {}).get("is_demo_illustrative"):
        labels.append(DEMO_LABEL)
    if mod.get("label"):
        labels.append(mod["label"])
    return {
        "schema": "calculation-report-v1",
        "generator_version": GENERATOR_VERSION,
        "labels": labels,
        "project": snap.get("project"),
        "reporting_period": snap.get("reporting_period"),
        "crediting_period": snap.get("crediting_period"),
        "methodology": snap.get("methodology"),
        "module": {k: mod.get(k) for k in ("code", "version", "readiness", "label", "steps", "constants", "variables")},
        "engine_version": run.engine_version,
        "dataset": {**(snap.get("dataset") or {}), "evidence": ds.get("evidence", []), "field_collections": len(collections),
                    "sampling_points": len(points)},
        "calculation_run": {"id": str(run.id), "run_code": run.run_code, "status_at_generation": run.status,
                            "approved_by": str(run.approved_by) if run.approved_by else None,
                            "approved_at": run.approved_at.isoformat() + "Z" if run.approved_at else None,
                            "recalculation_of_run_id": str(run.recalculation_of_run_id) if run.recalculation_of_run_id else None,
                            "input_sha256": run.input_sha256, "output_sha256": run.output_sha256, "net_result": run.net_result,
                            "net_unit": run.net_unit},
        "inputs": inputs,
        "outputs": cs.stored_output_records(db, run.id),
        "qa_reviews": reviews,
        "findings": findings,
    }


def lines(content: dict[str, Any]) -> list[str]:
    """Plain-text layout of the report (deterministic)."""
    run, meth, mod, ds = content["calculation_run"], content.get("methodology") or {}, content["module"], content["dataset"]
    p, mp, cp = content.get("project") or {}, content.get("reporting_period") or {}, content.get("crediting_period")
    out = ["CALCULATION REPORT", *[f"*** {lbl} ***" for lbl in content["labels"]], "",
           f"Run {run['run_code']} ({run['status_at_generation']} at generation) · approved {run['approved_at']} by user {run['approved_by']}",
           f"Project {p.get('code')} ({p.get('environment')}) · reporting period #{mp.get('number')} {mp.get('name')} "
           f"{mp.get('start')}..{mp.get('end')}",
           f"Crediting period: {cp['start'] + '..' + cp['end'] if cp else 'not specified'}",
           f"Methodology {meth.get('code')} v{meth.get('version_label')} · calculation rules v{meth.get('calculation_rules_version')} "
           f"· monitoring rules v{meth.get('monitoring_rules_version')}{' · DEMO illustrative' if meth.get('is_demo_illustrative') else ''}",
           f"Module {mod.get('code')} {mod.get('version')} ({mod.get('readiness')}) · engine {content['engine_version']}",
           f"Dataset {ds.get('code')} v{ds.get('version')} · snapshot SHA-256 {ds.get('snapshot_sha256')}",
           f"Input SHA-256  {run['input_sha256']}", f"Output SHA-256 {run['output_sha256']}",
           f"RESULT: {run['net_result']} {run['net_unit']}  —  {CALCULATED_LABEL}", "",
           "CALCULATION RULES"]
    out += [f"  {r['rule_code']} [{r['step']}] {r.get('equation_reference') or ''} {r.get('title') or ''}" for r in meth.get("calculation_rules", [])]
    out += ["", "STEPS"] + [f"  {s['step']}: {s['status']} {s.get('rule_code') or ''}" for s in mod.get("steps") or []]
    out += ["", "CONSTANTS"] + [f"  {c['code']} = {c['value']} {c['unit']} ({c['source_reference']})" for c in mod.get("constants") or []]
    out += ["", "INPUTS (frozen)"]
    for i in content["inputs"]:
        where = " · ".join(x for x in (i.get("field_collection"), i.get("sampling_point"), i.get("stratum")) if x)
        out.append(f"  #{i['seq']} {i['variable']} = {i['value']} {i['unit'] or ''} [{i['source_type']} {i['source_code'] or ''}"
                   f"{' v' + str(i['source_version']) if i.get('source_version') else ''}] {where}"
                   f"{' sha ' + i['source_sha256'] if i.get('source_sha256') else ''}")
    out += ["", "OUTPUTS"]
    for o in content["outputs"]:
        out.append(f"  #{o['seq']} {o['step']} {o['output_code']} = {o['value']} {o['unit']} (rule {o['rule_code']}; inputs {o['inputs']}; "
                   f"outputs {o['outputs']}){' FINAL' if o['is_final'] else ''}")
    out += ["", "QA REVIEWS"] + [f"  {r['result']} {r['completed_at']} by user {r['completed_by']}: {r['notes'] or ''}"
                                 for r in content["qa_reviews"]]
    out += ["", "FINDINGS"] + ([f"  {f['code']} {f['category']}{' BLOCKING' if f['blocking'] else ''} {f['status']}: {f['title']}"
                                for f in content["findings"]] or ["  none"])
    out += ["", f"MRV evidence items: {len(ds.get('evidence', []))} (checksums in the canonical JSON)", "",
            f"Generator {content['generator_version']}. This report is a deterministic rendering of the canonical JSON content.",
            "Calculated tCO2e is not verified and not issued. This report is not a verification report."]
    return out


def render_pdf(content: dict[str, Any]) -> bytes:
    return pdf.render(lines(content))


def _size(db: Session, run: CalculationRun) -> int:
    n_find = db.scalar(select(func.count()).select_from(CalculationFinding).where(CalculationFinding.run_id == run.id)) or 0
    return len(json.loads(run.input_snapshot or "{}").get("inputs", [])) + len(cs.outputs(db, run.id)) + n_find + len(cs.qa_reviews(db, run.id))


def generate(db: Session, ctx: RequestContext, principal: Principal, run_id: uuid.UUID) -> CalculationReport:
    run, p = cs.get_run(db, principal, run_id, P.CALCULATION_MANAGE)
    if run.status != "APPROVED":       # B7: official reports exist only for APPROVED runs (never for BLOCKED ones)
        raise Conflict(f"Official reports are generated only for APPROVED runs (this run is {run.status}).", error_code="RUN_NOT_APPROVED")
    if fw.sha256(json.loads(run.input_snapshot or "{}")) != run.input_sha256:
        raise Conflict("The frozen input snapshot does not match its SHA-256.", error_code="INPUT_SNAPSHOT_MISMATCH")
    records = cs.stored_output_records(db, run.id)
    if fw.output_hash(records, run.module_code or "", run.module_version or "", run.engine_version) != run.output_sha256:
        raise Conflict("The stored outputs do not match their SHA-256.", error_code="SNAPSHOT_MISMATCH")
    limit = get_settings().CALCULATION_REPORT_MAX_ROWS
    if _size(db, run) > limit:   # B11: synchronous generation only below the guard
        raise Conflict(f"The report would exceed {limit} rows; background generation is not available yet.", error_code="REPORT_TOO_LARGE")
    content = build_content(db, run)
    sha = fw.sha256(content)
    cur = current_report(db, run.id)
    if cur is not None and cur.content_sha256 == sha and cur.generator_version == GENERATOR_VERSION:
        raise Conflict(f"Report {cur.report_code} is already current: its content would be identical.", error_code="REPORT_UNCHANGED")
    data = render_pdf(content)
    code = next_code(db, "calculation_report", utcnow().year)
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=run.id, organization_id=p.organization_id,
                                           environment=run.environment, category=DocumentCategory.CALCULATION_REPORT.value,
                                           title=f"Calculation report {code} ({run.run_code})", filename=f"{code}.pdf", data=data)
    version = (db.scalar(select(func.max(CalculationReport.version)).where(CalculationReport.run_id == run.id)) or 0) + 1
    now = utcnow()
    if cur is not None:
        cur.status, cur.superseded_at = "SUPERSEDED", now
        db.flush()
    rep = CalculationReport(report_code=code, run_id=run.id, project_id=p.id, monitoring_period_id=run.monitoring_period_id, version=version,
                            generator_version=GENERATOR_VERSION, content=fw.canonical_json(content), content_sha256=sha, document_id=doc.id,
                            pdf_sha256=hashlib.sha256(data).hexdigest(), status="CURRENT", generated_by=principal.user_id,
                            environment=run.environment)
    db.add(rep)
    db.flush()
    if cur is not None:
        cur.superseded_by_report_id = rep.id
        record(db, ctx, "CALCULATION_REPORT_SUPERSEDED", "calculation_report", cur.id, {"status": "CURRENT"},
               {"status": "SUPERSEDED", "report_code": cur.report_code, "superseded_by": code}, None, organization_id=p.organization_id)
    record(db, ctx, "CALCULATION_REPORT_GENERATED", "calculation_report", rep.id, None,
           {"report_code": code, "run_code": run.run_code, "version": version, "generator_version": GENERATOR_VERSION, "content_sha256": sha,
            "pdf_sha256": rep.pdf_sha256, "document_id": doc.id, "input_sha256": run.input_sha256, "output_sha256": run.output_sha256,
            "net_result": run.net_result}, None, organization_id=p.organization_id)
    db.commit()
    return rep


def verify(db: Session, rep: CalculationReport) -> dict[str, Any]:
    """Tamper detection: stored content vs its hash, stored PDF vs its hash, re-rendered PDF vs stored PDF, and freshness."""
    problems: list[str] = []
    content = json.loads(rep.content)
    if fw.sha256(content) != rep.content_sha256:
        problems.append("the stored report content does not match its SHA-256")
    doc = db.get(Document, rep.document_id)
    v = db.scalars(select(DocumentVersion).where(DocumentVersion.document_id == rep.document_id, DocumentVersion.version == doc.current_version)
                   ).first() if doc else None
    stored_pdf_sha = None
    if v is None or doc is None or doc.category != DocumentCategory.CALCULATION_REPORT.value:
        problems.append("the report PDF document is missing")
    else:
        try:
            stored_pdf_sha = hashlib.sha256(get_storage().get(v.storage_key)).hexdigest()
        except Exception:
            problems.append("the report PDF could not be read back from storage")
        if stored_pdf_sha is not None and stored_pdf_sha != rep.pdf_sha256:
            problems.append("the stored PDF does not match the recorded PDF SHA-256")
        if v.checksum_sha256 != rep.pdf_sha256:
            problems.append("the document checksum does not match the recorded PDF SHA-256")
    if hashlib.sha256(render_pdf(content)).hexdigest() != rep.pdf_sha256:
        problems.append("re-rendering the stored content does not reproduce the PDF")
    run = db.get(CalculationRun, rep.run_id)
    stale = bool(run is None or fw.sha256(build_content(db, run)) != rep.content_sha256 or rep.generator_version != GENERATOR_VERSION)
    return {"report_id": str(rep.id), "report_code": rep.report_code, "valid": not problems, "problems": problems, "stale": stale,
            "content_sha256": rep.content_sha256, "pdf_sha256": rep.pdf_sha256, "stored_pdf_sha256": stored_pdf_sha,
            "generator_version": rep.generator_version, "current_generator_version": GENERATOR_VERSION}


def get_report(db: Session, principal: Principal, report_id: uuid.UUID) -> tuple[CalculationReport, CalculationRun]:
    rep = db.get(CalculationReport, report_id)
    if rep is None:
        raise NotFound("Calculation report not found.", error_code="CALCULATION_REPORT_NOT_FOUND")
    try:
        run, _ = cs.get_run(db, principal, rep.run_id)
    except NotFound:
        raise NotFound("Calculation report not found.", error_code="CALCULATION_REPORT_NOT_FOUND") from None
    return rep, run
