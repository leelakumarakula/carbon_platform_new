"""Methodology catalog and versioning (spec section 7.5, 9, 48).

Rules enforced here:
- a methodology belongs to one standard and covers activities offered under that standard
- versions move DRAFT → IN_REVIEW → APPROVED (→ SUPERSEDED / RETIRED), DRAFT → WITHDRAWN; nothing becomes APPROVED
  by itself and the approver must not be the person who submitted the version (separation of duties)
- rules (applicability, monitoring, calculation, general) can only be changed while the version is DRAFT; after
  that a change means a new version (optionally copied from an existing one). Each rule set has a revision counter
- every change is written to the append-only methodology_change_history and to the audit log
- no equation is implemented here; calculation readiness stays NOT_PRODUCTION_READY (Phase 7 decides per module)
"""
import json
import uuid
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.service import record, record_transition, to_json
from app.core.context import RequestContext
from app.core.errors import Conflict, NotFound, PermissionDenied, ValidationFailed
from app.models import (
    Activity,
    Methodology,
    MethodologyActivity,
    MethodologyApplicabilityRule,
    MethodologyCalculationRule,
    MethodologyChangeHistory,
    MethodologyDocument,
    MethodologyMonitoringRule,
    MethodologyRule,
    MethodologyVersion,
    Organization,
    Standard,
)
from app.models.base import utcnow
from app.models.documents import DocumentCategory
from app.schemas.methodologies import (
    ApplicabilityRuleIn,
    CalculationRuleIn,
    GeneralRuleIn,
    MethodologyIn,
    MethodologyUpdate,
    MonitoringRuleIn,
    VersionIn,
    VersionUpdate,
)
from app.security.permissions import P
from app.security.principal import Principal
from app.services import catalog_service, document_service
from app.services.workflows import METHODOLOGY_VERSION_MACHINE

ENTITY = "methodology"
RULE_MODELS: dict[str, Any] = {"applicability": MethodologyApplicabilityRule, "monitoring": MethodologyMonitoringRule,
                               "calculation": MethodologyCalculationRule, "general": MethodologyRule}
COUNTER = {"applicability": "rules_version", "general": "rules_version", "monitoring": "monitoring_rules_version",
           "calculation": "calculation_rules_version"}
DOC_CATEGORIES = {DocumentCategory.METHODOLOGY_DOCUMENT.value, DocumentCategory.OTHER.value}


# ---------------------------------------------------------------- helpers
def _change(db: Session, ctx: RequestContext, m: Methodology, v: MethodologyVersion | None, change_type: str, summary: str,
            old: dict[str, Any] | None = None, new: dict[str, Any] | None = None, reason: str | None = None) -> None:
    db.add(MethodologyChangeHistory(methodology_id=m.id, methodology_version_id=v.id if v else None, change_type=change_type,
                                    summary=summary, old_value=to_json(old), new_value=to_json(new), reason=reason,
                                    changed_by=ctx.user_id, request_id=ctx.request_id))
    record(db, ctx, change_type, ENTITY, m.id, old, {**(new or {}), **({"version_id": v.id, "version_label": v.version_label} if v else {})},
           reason)


def _require(principal: Principal, code: str) -> None:
    if not principal.has(code):
        raise PermissionDenied(details={"required_permission": code})


def get_methodology(db: Session, principal: Principal, methodology_id: uuid.UUID) -> Methodology:
    _require(principal, P.METHODOLOGIES_READ)
    m = db.get(Methodology, methodology_id)
    if m is None:
        raise NotFound("Methodology not found.", error_code="METHODOLOGY_NOT_FOUND")
    return m


def get_version(db: Session, principal: Principal, version_id: uuid.UUID) -> tuple[Methodology, MethodologyVersion]:
    _require(principal, P.METHODOLOGIES_READ)
    v = db.scalars(select(MethodologyVersion).where(MethodologyVersion.id == version_id).execution_options(populate_existing=True)).first()
    if v is None:
        raise NotFound("Methodology version not found.", error_code="METHODOLOGY_VERSION_NOT_FOUND")
    m = db.get(Methodology, v.methodology_id)
    assert m is not None
    return m, v


def _document_resolver(db: Session, principal: Principal, methodology_id: uuid.UUID, kind: str) -> None:
    if db.get(Methodology, methodology_id) is None or not principal.has(P.METHODOLOGIES_MANAGE if kind == "manage" else P.METHODOLOGIES_READ):
        raise NotFound("Document not found.", error_code="DOCUMENT_NOT_FOUND")


document_service.register_resolver(ENTITY, _document_resolver)


def activity_ids(db: Session, methodology_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(MethodologyActivity.activity_id).where(MethodologyActivity.methodology_id == methodology_id)).all())


def versions(db: Session, methodology_id: uuid.UUID) -> list[MethodologyVersion]:
    return list(db.scalars(select(MethodologyVersion).where(MethodologyVersion.methodology_id == methodology_id)
                           .order_by(MethodologyVersion.version_number.desc())).all())


def rules(db: Session, version_id: uuid.UUID) -> dict[str, list[Any]]:
    return {kind: list(db.scalars(select(model).where(model.methodology_version_id == version_id)
                                  .order_by(model.sort_order, model.rule_code)).all()) for kind, model in RULE_MODELS.items()}


def list_methodologies(db: Session, principal: Principal, environment: str | None = None, standard_id: uuid.UUID | None = None
                       ) -> list[Methodology]:
    _require(principal, P.METHODOLOGIES_READ)
    stmt = select(Methodology)
    if environment:
        stmt = stmt.where(Methodology.environment == environment)
    if standard_id:
        stmt = stmt.where(Methodology.standard_id == standard_id)
    return list(db.scalars(stmt.order_by(Methodology.code)).all())


# ---------------------------------------------------------------- methodologies
def create_methodology(db: Session, ctx: RequestContext, principal: Principal, data: MethodologyIn) -> Methodology:
    _require(principal, P.METHODOLOGIES_MANAGE)
    std = db.get(Standard, data.standard_id)
    if std is None:
        raise NotFound("Standard not found.", error_code="STANDARD_NOT_FOUND")
    if std.environment != data.environment:
        raise Conflict("Demo and live records cannot be mixed.", error_code="ENVIRONMENT_MISMATCH")
    if db.scalars(select(Methodology).where(Methodology.code == data.code)).first():
        raise Conflict(f"A methodology with code {data.code} already exists.", error_code="CODE_EXISTS")
    for aid in data.activity_ids:
        a = db.get(Activity, aid)
        if a is None or a.environment != data.environment:
            raise ValidationFailed("Activity not found.", error_code="ACTIVITY_NOT_FOUND")
        if not catalog_service.is_linked(db, std.id, aid):
            raise ValidationFailed(f"{a.name} is not offered under {std.name}.", error_code="ACTIVITY_NOT_IN_STANDARD")
    m = Methodology(created_by=principal.user_id, **data.model_dump(exclude={"activity_ids"}))
    db.add(m)
    db.flush()
    for aid in data.activity_ids:
        db.add(MethodologyActivity(methodology_id=m.id, activity_id=aid))
    _change(db, ctx, m, None, "METHODOLOGY_CREATED", f"Methodology {m.code} created",
            None, {"code": m.code, "name": m.name, "standard_id": std.id, "activity_ids": data.activity_ids, "environment": m.environment})
    db.commit()
    return m


def update_methodology(db: Session, ctx: RequestContext, principal: Principal, methodology_id: uuid.UUID, data: MethodologyUpdate) -> Methodology:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m = get_methodology(db, principal, methodology_id)
    changes = data.model_dump(exclude_unset=True, exclude={"reason"})
    old = {k: getattr(m, k) for k in changes}
    for k, v in changes.items():
        setattr(m, k, v)
    if old != changes:
        _change(db, ctx, m, None, "METHODOLOGY_UPDATED", f"Methodology {m.code} metadata changed", old, changes, data.reason)
    db.commit()
    return m


# ---------------------------------------------------------------- versions
def create_version(db: Session, ctx: RequestContext, principal: Principal, methodology_id: uuid.UUID, data: VersionIn) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m = get_methodology(db, principal, methodology_id)
    if any(v.version_label == data.version_label for v in versions(db, m.id)):
        raise Conflict(f"Version {data.version_label} already exists.", error_code="VERSION_EXISTS")
    base = None
    if data.based_on_version_id:
        base = db.get(MethodologyVersion, data.based_on_version_id)
        if base is None or base.methodology_id != m.id:
            raise ValidationFailed("The version to copy must belong to this methodology.", error_code="INVALID_BASE_VERSION")
    number = (db.scalar(select(func.max(MethodologyVersion.version_number)).where(MethodologyVersion.methodology_id == m.id)) or 0) + 1
    v = MethodologyVersion(methodology_id=m.id, version_number=number, created_by=principal.user_id, is_demo_illustrative=m.environment == "DEMO",
                           rules_version=base.rules_version if base else 1,
                           monitoring_rules_version=base.monitoring_rules_version if base else 1,
                           calculation_rules_version=base.calculation_rules_version if base else 1, **data.model_dump())
    db.add(v)
    db.flush()
    copied = 0
    if base:
        for kind, model in RULE_MODELS.items():
            for r in rules(db, base.id)[kind]:
                cols = {c.key: getattr(r, c.key) for c in model.__table__.columns if c.key not in ("id", "methodology_version_id", "created_at")}
                db.add(model(methodology_version_id=v.id, **cols))
                copied += 1
    _change(db, ctx, m, v, "METHODOLOGY_VERSION_CREATED", f"Draft version {v.version_label} created"
            + (f" from version {base.version_label} ({copied} rules copied)" if base else ""),
            None, {"version_number": number, "status": "DRAFT", "based_on_version_id": base.id if base else None})
    db.commit()
    return v


def _draft(v: MethodologyVersion, what: str) -> None:
    if v.status != "DRAFT":
        raise Conflict(f"{what} is only possible on a DRAFT version (this one is {v.status}). Create a new version instead.",
                       error_code="VERSION_NOT_EDITABLE")


def update_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, data: VersionUpdate) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _draft(v, "Editing version details")
    changes = data.model_dump(exclude_unset=True)
    eff_from, eff_to = changes.get("effective_from", v.effective_from), changes.get("effective_to", v.effective_to)
    if eff_from and eff_to and eff_to < eff_from:
        raise ValidationFailed("effective_to is before effective_from.", error_code="INVALID_DATES")
    old = {k: getattr(v, k) for k in changes}
    for k, val in changes.items():
        setattr(v, k, val)
    if old != changes:
        _change(db, ctx, m, v, "METHODOLOGY_VERSION_UPDATED", f"Version {v.version_label} details changed", old, changes)
    db.commit()
    return v


def _bump(db: Session, v: MethodologyVersion, kind: str) -> None:
    """A rule set copied from another version gets a new revision number the first time it changes."""
    attr = COUNTER[kind]
    base = db.get(MethodologyVersion, v.based_on_version_id) if v.based_on_version_id else None
    if base is not None and getattr(v, attr) == getattr(base, attr):
        setattr(v, attr, getattr(base, attr) + 1)


def add_rule(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, kind: str,
             data: ApplicabilityRuleIn | MonitoringRuleIn | CalculationRuleIn | GeneralRuleIn) -> Any:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _draft(v, "Changing rules")
    model = RULE_MODELS[kind]
    if any(r.rule_code == data.rule_code for r in rules(db, v.id)[kind]):
        raise Conflict(f"Rule {data.rule_code} already exists in this version.", error_code="RULE_EXISTS")
    values = data.model_dump()
    if kind == "applicability":
        # Stored wrapped ({"value": …}) so scalars pass SQL Server's ISJSON check.
        values["expected_value"] = json.dumps({"value": values["expected_value"]}) if values["expected_value"] is not None else None
        _validate_applicability(values)
    if kind == "general":
        values["parameters"] = json.dumps(values["parameters"]) if values["parameters"] is not None else None
    r = model(methodology_version_id=v.id, **values)
    db.add(r)
    _bump(db, v, kind)
    db.flush()
    _change(db, ctx, m, v, "METHODOLOGY_RULE_ADDED", f"{kind.title()} rule {r.rule_code} added to version {v.version_label}",
            None, {"kind": kind, "rule_code": r.rule_code, **{k: values[k] for k in values if k not in ("description",)}})
    db.commit()
    return r


def expected_value(stored: str | None) -> Any:
    return json.loads(stored)["value"] if stored else None


def _validate_applicability(values: dict[str, Any]) -> None:
    from app.rules.methodology_engine import RuleError, check
    op = values["operator"]
    expected = expected_value(values["expected_value"])
    needs_value = op not in ("EXISTS", "IS_TRUE", "IS_FALSE")
    if needs_value and expected is None:
        raise ValidationFailed(f"Operator {op} needs an expected value.", error_code="INVALID_RULE")
    if op == "BETWEEN" and not (isinstance(expected, list) and len(expected) == 2):
        raise ValidationFailed("BETWEEN needs [minimum, maximum].", error_code="INVALID_RULE")
    if op in ("IN", "NOT_IN", "ANY_IN", "ALL_IN", "NONE_IN") and not isinstance(expected, list):
        raise ValidationFailed(f"{op} needs a list of values.", error_code="INVALID_RULE")
    if op in ("DATE_ON_OR_AFTER", "DATE_ON_OR_BEFORE"):
        try:
            check(op, expected, expected)
        except (RuleError, ValueError) as e:
            raise ValidationFailed("Give the date as YYYY-MM-DD.", error_code="INVALID_RULE") from e


def delete_rule(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, kind: str, rule_id: uuid.UUID,
                reason: str) -> None:
    """Only draft rules (never used by any evaluation) can be removed; the removal is in the change history."""
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _draft(v, "Changing rules")
    r = db.get(RULE_MODELS[kind], rule_id)
    if r is None or r.methodology_version_id != v.id:
        raise NotFound("Rule not found.", error_code="RULE_NOT_FOUND")
    old = {c.key: getattr(r, c.key) for c in r.__table__.columns if c.key not in ("id", "methodology_version_id")}
    db.delete(r)
    _bump(db, v, kind)
    _change(db, ctx, m, v, "METHODOLOGY_RULE_REMOVED", f"{kind.title()} rule {old['rule_code']} removed from draft {v.version_label}",
            old, None, reason)
    db.commit()


def _transition(db: Session, ctx: RequestContext, m: Methodology, v: MethodologyVersion, target: str, action: str, reason: str) -> None:
    record_transition(db, ctx, METHODOLOGY_VERSION_MACHINE, v.id, v.status, target, action, reason)
    db.add(MethodologyChangeHistory(methodology_id=m.id, methodology_version_id=v.id, change_type=action,
                                    summary=f"Version {v.version_label}: {v.status} → {target}", old_value=to_json({"status": v.status}),
                                    new_value=to_json({"status": target}), reason=reason, changed_by=ctx.user_id, request_id=ctx.request_id))
    v.status, v.status_reason = target, reason


def submit_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    missing = []
    if not rules(db, v.id)["applicability"]:
        missing.append("at least one applicability rule")
    if not (v.source_url or v.source_document_id or v.source_name):
        missing.append("the authoritative source (name, URL or document)")
    if v.effective_from is None:
        missing.append("an effective date")
    unclassified = [r.rule_code for r in rules(db, v.id)["monitoring"] if r.measurement_source == "UNCLASSIFIED"]
    if unclassified:
        missing.append("a measurement source (FIELD / FIELD_ACTIVITY / LABORATORY) for monitoring rule(s) " + ", ".join(unclassified))
    if missing:
        raise Conflict("Cannot submit yet: " + "; ".join(missing) + ".", error_code="REQUIREMENTS_NOT_MET", details={"missing": missing})
    _transition(db, ctx, m, v, "IN_REVIEW", "METHODOLOGY_VERSION_SUBMITTED", reason)
    v.submitted_by, v.submitted_at = principal.user_id, utcnow()
    db.commit()
    return v


def approve_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str,
                    supersedes_version_id: uuid.UUID | None) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_APPROVE)
    m, v = get_version(db, principal, version_id)
    if v.submitted_by == principal.user_id:
        raise PermissionDenied("You submitted this version, so someone else must approve it.", error_code="SEPARATION_OF_DUTIES")
    old = None
    if supersedes_version_id:
        old = db.get(MethodologyVersion, supersedes_version_id)
        if old is None or old.methodology_id != m.id or old.status != "APPROVED" or old.id == v.id:
            raise ValidationFailed("Only another approved version of this methodology can be superseded.", error_code="INVALID_SUPERSEDE")
    # decision V2-A: also enforced here for versions that were already IN_REVIEW when migration 0008 marked a rule UNCLASSIFIED
    unclassified = [r.rule_code for r in rules(db, v.id)["monitoring"] if r.measurement_source == "UNCLASSIFIED"]
    if unclassified:
        raise Conflict("Cannot approve: monitoring rule(s) " + ", ".join(unclassified) + " declare no measurement source (FIELD / "
                       "FIELD_ACTIVITY / LABORATORY). Return the version so a specialist can classify them.",
                       error_code="MEASUREMENT_SOURCE_UNCLASSIFIED", details={"rules": unclassified})
    _transition(db, ctx, m, v, "APPROVED", "METHODOLOGY_VERSION_APPROVED", reason)
    v.approved_by, v.approved_at = principal.user_id, utcnow()
    if old is not None:
        _transition(db, ctx, m, old, "SUPERSEDED", "METHODOLOGY_VERSION_SUPERSEDED", f"Superseded by version {v.version_label}: {reason}")
        old.superseded_at, old.superseded_by_id = utcnow(), v.id
    db.commit()
    return v


def return_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_APPROVE)
    m, v = get_version(db, principal, version_id)
    _transition(db, ctx, m, v, "DRAFT", "METHODOLOGY_VERSION_RETURNED", reason)
    db.commit()
    return v


def retire_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _transition(db, ctx, m, v, "RETIRED", "METHODOLOGY_VERSION_RETIRED", reason)
    v.effective_to = v.effective_to or utcnow().date()
    db.commit()
    return v


def withdraw_version(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _transition(db, ctx, m, v, "WITHDRAWN", "METHODOLOGY_VERSION_WITHDRAWN", reason)
    db.commit()
    return v


# ---------------------------------------------------------------- documents / history
def upload_document(db: Session, ctx: RequestContext, principal: Principal, methodology_id: uuid.UUID, version_id: uuid.UUID | None,
                    category: str, title: str, filename: str | None, data: bytes, as_source: bool) -> uuid.UUID:
    _require(principal, P.METHODOLOGIES_MANAGE)
    m = get_methodology(db, principal, methodology_id)
    if category not in DOC_CATEGORIES:
        raise ValidationFailed("Use METHODOLOGY_DOCUMENT or OTHER.", error_code="INVALID_CATEGORY")
    v = None
    if version_id:
        _, v = get_version(db, principal, version_id)
        if v.methodology_id != m.id:
            raise ValidationFailed("The version belongs to another methodology.", error_code="INVALID_VERSION")
    platform = db.scalars(select(Organization).where(Organization.code == "PLATFORM")).one()
    doc = document_service.create_document(db, ctx, entity_type=ENTITY, entity_id=m.id, organization_id=platform.id,
                                           environment=m.environment, category=category, title=title, filename=filename, data=data)
    db.add(MethodologyDocument(methodology_id=m.id, document_id=doc.id, methodology_version_id=v.id if v else None))
    if as_source and v is not None:
        _draft(v, "Setting the source document")
        v.source_document_id = doc.id
    _change(db, ctx, m, v, "METHODOLOGY_DOCUMENT_ADDED", f"Document '{doc.title}' added" + (" as version source" if as_source else ""),
            None, {"document_id": doc.id, "category": category})
    db.commit()
    return doc.id


def history(db: Session, principal: Principal, methodology_id: uuid.UUID) -> list[MethodologyChangeHistory]:
    m = get_methodology(db, principal, methodology_id)
    return list(db.scalars(select(MethodologyChangeHistory).where(MethodologyChangeHistory.methodology_id == m.id)
                           .order_by(MethodologyChangeHistory.id.desc())).all())


# ---------------------------------------------------------------- calculation module selection (Calculation tab)
def compatible_modules(db: Session, principal: Principal, version_id: uuid.UUID) -> tuple[Methodology, MethodologyVersion, list[Any]]:
    """Registered modules with their compatibility for this version (same methodology code and version label)."""
    from app.calculation import registry
    m, v = get_version(db, principal, version_id)
    return m, v, [(mod, registry.implements(mod, m.code, v.version_label)) for mod in registry.modules()]


def select_calculation_module(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, module_code: str | None,
                              reason: str) -> MethodologyVersion:
    """Choose (or clear) the calculation module of a DRAFT version. Choosing copies the module's rule set into the version:
    its calculation rules replace the draft's calculation rules, its monitoring rules are added (an existing rule with the same code
    must declare the same unit and measurement source), and its SAMPLING parameters are added as one general rule. The version's
    approval approves the choice; the calculation engine then binds the module to this version."""
    from app.calculation import registry
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    _draft(v, "Choosing the calculation module")
    old = {"calculation_module_code": v.calculation_module_code}
    if module_code is None:
        v.calculation_module_code = None
        _change(db, ctx, m, v, "METHODOLOGY_CALCULATION_MODULE_CLEARED", f"Calculation module cleared on draft {v.version_label}", old,
                {"calculation_module_code": None}, reason)
        db.commit()
        return v
    mod = registry.by_code(module_code)
    if mod is None:
        raise NotFound("No such calculation module.", error_code="MODULE_NOT_FOUND")
    if not registry.implements(mod, m.code, v.version_label):
        raise ValidationFailed(f"Module {mod.code} implements {mod.methodology_code} {mod.version_label}, not {m.code} {v.version_label}.",
                               error_code="MODULE_NOT_FOR_VERSION")
    current = rules(db, v.id)
    # monitoring rules: add the missing ones; refuse silently different definitions
    existing = {r.rule_code: r for r in current["monitoring"]}
    conflicts = [d["rule_code"] for d in mod.monitoring_rule_definitions if d["rule_code"] in existing
                 and ((existing[d["rule_code"]].unit or None) != (d.get("unit") or None)
                      or existing[d["rule_code"]].measurement_source != d["measurement_source"])]
    if conflicts:
        raise Conflict("These monitoring rules already exist with a different unit or measurement source: " + ", ".join(conflicts) + ".",
                       error_code="MONITORING_RULE_CONFLICT", details={"rule_codes": conflicts})
    added_monitoring = []
    for d in mod.monitoring_rule_definitions:
        r = existing.get(d["rule_code"])
        if r is None:
            db.add(MethodologyMonitoringRule(methodology_version_id=v.id, rule_code=d["rule_code"], title=d["title"], parameter=d["parameter"],
                                             measurement_source=d["measurement_source"], unit=d.get("unit"), frequency=d.get("frequency"),
                                             method=d.get("method"), data_level=d.get("data_level"),
                                             source_reference=d.get("source_reference"), description=f"Required by module {mod.code}"))
            added_monitoring.append(d["rule_code"])
        elif r.data_level is None and d.get("data_level"):
            r.data_level = d["data_level"]
    if added_monitoring:
        _bump(db, v, "monitoring")
    # calculation rules: exactly the module's
    for r in current["calculation"]:
        db.delete(r)
    db.flush()
    for i, d in enumerate(mod.calculation_rule_definitions):
        db.add(MethodologyCalculationRule(methodology_version_id=v.id, rule_code=d["rule_code"], title=d["title"], step=d["step"],
                                          equation_reference=d.get("equation_reference"), sort_order=i + 1,
                                          implementation_status="NOT_PRODUCTION_READY" if mod.readiness != "PRODUCTION_READY" else "VERIFIED",
                                          description=f"Implemented by module {mod.code} {mod.version}"))
    _bump(db, v, "calculation")
    # sampling parameters: one general SAMPLING rule (kept if the specialist already configured one with this code)
    smp_code = "MODULE-SAMPLING"
    if mod.sampling_parameters and not any(r.rule_code == smp_code for r in current["general"]):
        db.add(MethodologyRule(methodology_version_id=v.id, rule_code=smp_code, title=f"Sampling parameters required by {mod.code}",
                               rule_type="SAMPLING", parameters=json.dumps(mod.sampling_parameters),
                               source_reference=", ".join(sorted({d["rule_code"] for d in mod.calculation_rule_definitions}))))
        _bump(db, v, "general")
    v.calculation_module_code = mod.code
    db.flush()
    _change(db, ctx, m, v, "METHODOLOGY_CALCULATION_MODULE_SELECTED", f"Calculation module {mod.code} {mod.version} selected on draft "
            f"{v.version_label}", old, {"calculation_module_code": mod.code, "module_version": mod.version, "readiness": mod.readiness,
                                      "calculation_rules": [d["rule_code"] for d in mod.calculation_rule_definitions],
                                      "monitoring_rules_added": added_monitoring}, reason)
    db.commit()
    return v


# ---------------------------------------------------------------- production readiness of the selected calculation module
READINESS_REQUESTED, READINESS_APPROVED, READINESS_REVOKED = (
    "CALCULATION_READINESS_REQUESTED", "CALCULATION_READINESS_APPROVED", "CALCULATION_READINESS_REVOKED")


def readiness_request(db: Session, version_id: uuid.UUID) -> MethodologyChangeHistory | None:
    """The open readiness request of a version: the latest REQUESTED entry not followed by an APPROVED / REVOKED one."""
    entries = db.scalars(select(MethodologyChangeHistory).where(
        MethodologyChangeHistory.methodology_version_id == version_id,
        MethodologyChangeHistory.change_type.in_([READINESS_REQUESTED, READINESS_APPROVED, READINESS_REVOKED]))
        .order_by(MethodologyChangeHistory.id.desc())).all()
    return entries[0] if entries and entries[0].change_type == READINESS_REQUESTED else None


def request_calculation_readiness(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, evidence: str) -> MethodologyVersion:
    """A methodology specialist asks for the selected module to be declared production-ready, citing the verification evidence
    (expert review of the equations, worked-example tests). Only an APPROVED version with a selected module qualifies."""
    _require(principal, P.METHODOLOGIES_MANAGE)
    m, v = get_version(db, principal, version_id)
    if v.status != "APPROVED" or not v.calculation_module_code:
        raise Conflict("Production readiness is requested for an APPROVED version that has a calculation module selected.",
                       error_code="READINESS_NOT_APPLICABLE")
    if v.calculation_readiness == "PRODUCTION_READY":
        raise Conflict("The calculation is already production-ready.", error_code="ALREADY_PRODUCTION_READY")
    if readiness_request(db, v.id) is not None:
        raise Conflict("A readiness request is already open.", error_code="READINESS_REQUEST_OPEN")
    _change(db, ctx, m, v, READINESS_REQUESTED, f"Production readiness requested for {v.calculation_module_code} on version {v.version_label}",
            {"calculation_readiness": v.calculation_readiness}, {"module": v.calculation_module_code}, evidence)
    db.commit()
    return v


def decide_calculation_readiness(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, approve: bool,
                                 notes: str) -> MethodologyVersion:
    """Approve (someone other than the requester) or reject the open request."""
    _require(principal, P.METHODOLOGIES_APPROVE)
    m, v = get_version(db, principal, version_id)
    req = readiness_request(db, v.id)
    if req is None:
        raise Conflict("There is no open readiness request.", error_code="NO_READINESS_REQUEST")
    if req.changed_by == principal.user_id:
        raise PermissionDenied("You requested production readiness, so someone else must decide.", error_code="SEPARATION_OF_DUTIES")
    old = {"calculation_readiness": v.calculation_readiness}
    if approve:
        v.calculation_readiness = "PRODUCTION_READY"
    _change(db, ctx, m, v, READINESS_APPROVED if approve else READINESS_REVOKED,
            f"Production readiness {'approved' if approve else 'rejected'} for {v.calculation_module_code} on version {v.version_label}",
            old, {"calculation_readiness": v.calculation_readiness, "module": v.calculation_module_code}, notes)
    db.commit()
    return v


def revoke_calculation_readiness(db: Session, ctx: RequestContext, principal: Principal, version_id: uuid.UUID, reason: str) -> MethodologyVersion:
    _require(principal, P.METHODOLOGIES_APPROVE)
    m, v = get_version(db, principal, version_id)
    if v.calculation_readiness != "PRODUCTION_READY":
        raise Conflict("The calculation is not production-ready.", error_code="NOT_PRODUCTION_READY")
    v.calculation_readiness = "NOT_PRODUCTION_READY"
    _change(db, ctx, m, v, READINESS_REVOKED, f"Production readiness revoked for {v.calculation_module_code} on version {v.version_label}",
            {"calculation_readiness": "PRODUCTION_READY"}, {"calculation_readiness": "NOT_PRODUCTION_READY"}, reason)
    db.commit()
    return v
