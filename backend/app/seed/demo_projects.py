"""DEMO standards/activities and 2 DEMO projects (spec section 43), created through the real services on top of the
DEMO farmers and farms. Everything belongs to DEMO organizations (environment=DEMO).

No methodology is selected, nothing is calculated, verified or issued. The DEMO catalog entries are illustrative
reference entries for demonstration only — they are not statements about any programme's actual eligibility rules.
"""
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Farm, Farmer, Organization, Project, Standard
from app.schemas.farmers import AgreementCreate
from app.schemas.projects import (
    ActivityIn,
    ActivitySelect,
    BaselineIn,
    CarbonRightIn,
    CreditingPeriodIn,
    ParticipantIn,
    ProjectCreate,
    ProjectFarmIn,
    StandardIn,
    StandardSelect,
)
from app.seed.demo_farms import PDF, _actor
from app.services import catalog_service, farmer_service, project_farm_service, project_service

CATALOG_NOTE = "DEMO reference entry for demonstrations only; confirm all programme details against the official source."
STANDARDS = [
    StandardIn(code="DEMO-VCS", name="Verified Carbon Standard (DEMO reference entry)", owner_name="Verra", program_type="VOLUNTARY",
               description=CATALOG_NOTE, source_url="https://verra.org/methodologies/vm0042-improved-agricultural-land-management-v2-2/",
               environment="DEMO"),
    StandardIn(code="DEMO-CCTS-OFFSET", name="India CCTS Offset Mechanism (DEMO reference entry)", owner_name="Bureau of Energy Efficiency",
               program_type="COMPLIANCE", description=CATALOG_NOTE,
               source_url="https://beeindia.gov.in/sites/default/files/Detailed%20Procedure%20for%20Offset%20Mechanism_CCTS.pdf",
               environment="DEMO"),
]
ACTIVITIES = [
    ("DEMO-ALM-TILLAGE", "Improved agricultural land management: reduced tillage (DEMO)", ["DEMO-VCS", "DEMO-CCTS-OFFSET"]),
    ("DEMO-ALM-RESIDUE", "Improved agricultural land management: residue retention (DEMO)", ["DEMO-VCS", "DEMO-CCTS-OFFSET"]),
    ("DEMO-ALM-NUTRIENT", "Improved agricultural land management: nutrient management (DEMO)", ["DEMO-VCS"]),
]
TEAM = [("mrv", "MRV_MANAGER"), ("gis", "GIS_SPECIALIST"), ("qa", "QA_OFFICER"), ("supervisor", "FIELD_SUPERVISOR"),
        ("finance", "FINANCE_MANAGER"), ("methodology", "METHODOLOGY_SPECIALIST")]


def _catalog(db: Session) -> dict[str, object]:
    meth, meth_ctx = _actor(db, "methodology")
    out: dict[str, object] = {}
    for s in STANDARDS:
        existing = db.scalars(select(Standard).where(Standard.code == s.code)).first()
        out[s.code] = existing.id if existing else catalog_service.create_standard(db, meth_ctx, meth, s).id
    from app.models import Activity
    for code, name, stds in ACTIVITIES:
        existing_a = db.scalars(select(Activity).where(Activity.code == code)).first()
        out[code] = existing_a.id if existing_a else catalog_service.create_activity(
            db, meth_ctx, meth, ActivityIn(code=code, name=name, category="AGRICULTURAL_LAND_MANAGEMENT", description=CATALOG_NOTE,
                                           environment="DEMO", standard_ids=[out[c] for c in stds])).id  # type: ignore[misc]
    return out


def _signed_agreement(db: Session, farmer: Farmer) -> object:
    pm, ctx = _actor(db, "pm")
    f = farmer_service.create_agreement(db, ctx, pm, farmer.id, AgreementCreate(
        agreement_type="CARBON_PROJECT_PARTICIPATION", template_version="DEMO-CPA-1",
        terms_summary="DEMO agreement: participation and carbon-rights reference for demonstration only.",
        effective_from=date(2026, 6, 1)))
    ag = f.agreements[-1]
    doc = farmer_service.upload_document(db, ctx, pm, farmer.id, "AGREEMENT", "DEMO signed agreement", "agreement.pdf", PDF)
    farmer_service.sign_agreement(db, ctx, pm, farmer.id, ag.id, doc, "PAPER_SIGNED")
    return ag.id


def seed_demo_projects(db: Session) -> dict[str, int]:
    org = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    if db.scalars(select(Project).where(Project.organization_id == org.id)).first():
        return {"projects": 0, "standards": 0, "activities": 0}
    cat = _catalog(db)
    pm, pm_ctx = _actor(db, "pm")
    qa, qa_ctx = _actor(db, "qa")
    gis, gis_ctx = _actor(db, "gis")
    farms = db.scalars(select(Farm).where(Farm.organization_id == org.id, Farm.status == "VERIFIED").order_by(Farm.farm_code)).all()
    agreements = {f.farmer_id: None for f in farms}
    for fid in agreements:
        farmer = db.get(Farmer, fid)
        if farmer is not None:
            agreements[fid] = _signed_agreement(db, farmer)  # type: ignore[assignment]

    def build(name: str, region: str, farm_slice: list[Farm], standard: str, activity: str) -> Project:
        p = project_service.create_project(db, pm_ctx, pm, ProjectCreate(
            organization_id=org.id, name=name, description="DEMO project for demonstration only. No methodology selected; nothing calculated.",
            project_type="AGRICULTURAL_LAND_MANAGEMENT", country="IN", region=region, start_date=date(2026, 6, 1)))
        for local, role in TEAM:
            u, _ = _actor(db, local)
            project_service.add_participant(db, pm_ctx, pm, p.id, ParticipantIn(user_id=u.user_id, project_role=role))  # type: ignore[arg-type]
        project_service.start_data_collection(db, pm_ctx, pm, p.id, "DEMO: collecting farm and baseline data")
        for f in farm_slice:
            project_farm_service.add_farm(db, pm_ctx, pm, p.id, ProjectFarmIn(
                farm_id=f.id, participation_start=date(2026, 6, 1),
                carbon_rights=CarbonRightIn(holder_type="FARMER", agreement_id=agreements[f.farmer_id],  # type: ignore[arg-type]
                                            reference="DEMO carbon-rights clause of the participation agreement",
                                            effective_from=date(2026, 6, 1))))
        project_service.select_standard(db, pm_ctx, pm, p.id, StandardSelect(standard_id=cat[standard]))  # type: ignore[arg-type]
        project_service.select_activity(db, pm_ctx, pm, p.id, ActivitySelect(activity_id=cat[activity]))  # type: ignore[arg-type]
        project_service.add_crediting_period(db, pm_ctx, pm, p.id, CreditingPeriodIn(start_date=date(2026, 6, 1), end_date=date(2036, 5, 31),
                                                                                       notes="DEMO proposed period; to be validated in Phase 4"))
        project_service.update_baseline(db, pm_ctx, pm, p.id, BaselineIn(
            period_start=date(2021, 6, 1), period_end=date(2026, 5, 31),
            description="DEMO: conventional tillage with residue burning (from recorded farm history)",
            data_sources="Farm land/crop/practice history records (DEMO)"))
        project_service.upload_document(db, pm_ctx, pm, p.id, "PROJECT_DESIGN", "DEMO project design summary", "design.pdf", PDF)
        return p

    build("Nashik soil health pilot (DEMO)", "Pimpalgaon–Ozar, Nashik", list(farms[:3]), "DEMO-VCS", "DEMO-ALM-TILLAGE")
    b = build("Niphad residue retention programme (DEMO)", "Ozar–Niphad, Nashik", list(farms[3:6]), "DEMO-CCTS-OFFSET", "DEMO-ALM-RESIDUE")
    # Project B goes through the real eligibility workflow: submit → GIS boundary review → QA verifies carbon rights →
    # QA approves eligibility (STANDARD_SELECTED) → PM confirms the activity (ACTIVITY_SELECTED). No verification of credits.
    project_service.submit(db, pm_ctx, pm, b.id, "DEMO: project data complete")
    project_farm_service.review_boundary(db, gis_ctx, gis, b.id, "ACCEPTED", "DEMO: union of verified farm polygons checked")
    from app.repositories import projects as repo
    for cr in repo.carbon_rights(db, b.id):
        project_farm_service.review_carbon_right(db, qa_ctx, qa, b.id, cr.id, "VERIFIED", "DEMO: signed agreement on file")
    project_service.approve_eligibility(db, qa_ctx, qa, b.id, "DEMO: eligibility data complete for the selected route")
    project_service.confirm_activity(db, pm_ctx, pm, b.id, "DEMO: activity confirmed")
    return {"projects": 2, "standards": len(STANDARDS), "activities": len(ACTIVITIES)}
