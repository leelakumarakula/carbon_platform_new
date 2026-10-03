"""DEMO MRV data on the DEMO project whose methodology version is locked (Niphad), created through the real services.

Shows an MRV plan (CONFIGURATION_REQUIRED acknowledged — the DEMO methodology configures no sampling rules), a
monitoring period in DATA_COLLECTION, two strata, an approved sampling design, generated points assigned to
collector@demo, two accepted field collections, one submitted, monitoring records, DEMO placeholder photos and an
MRV dataset that is still COLLECTING. There are NO laboratory results, NO calculations and NO credits.
"""
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MrvPlan, Project
from app.repositories import projects as project_repo
from app.schemas.mrv import (
    AllocationIn,
    CharacteristicIn,
    CollectionUpdate,
    DatasetIn,
    DesignIn,
    MeasurementIn,
    MonitoringRecordIn,
    PeriodIn,
    PlanIn,
    StratumIn,
)
from app.seed.demo_farms import _actor
from app.services import field_rules, mrv_service, sampling_service

# 1×1 PNG, clearly a DEMO placeholder (not a real field photo)
DEMO_PNG = bytes.fromhex("89504e470d0a1a0a0000000d4948445200000001000000010806000000"
                         "1f15c4890000000d49444154789c6360f8cf00000301010018dd8db40000000049454e44ae426082")


def seed_demo_mrv(db: Session) -> dict[str, int]:
    p = db.scalars(select(Project).where(Project.environment == "DEMO", Project.methodology_status == "CONFIRMED",
                                         Project.name.like("Niphad%"))).first()
    if p is None or db.scalars(select(MrvPlan).where(MrvPlan.project_id == p.id)).first():
        return {"plans": 0, "points": 0, "collections": 0}
    mrv, mrv_ctx = _actor(db, "mrv")
    qa, qa_ctx = _actor(db, "qa")
    gis, gis_ctx = _actor(db, "gis")
    sup, sup_ctx = _actor(db, "supervisor")
    col, col_ctx = _actor(db, "collector")

    plan = mrv_service.create_plan(db, mrv_ctx, mrv, PlanIn(
        project_id=p.id, monitoring_frequency="Once per monitoring period (DEMO)", monitoring_start=date(2026, 6, 1),
        monitoring_end=date(2036, 5, 31), quantification_approach="MEASURE_AND_REMEASURE",
        required_evidence="Field photo per sample; practice records per farm (DEMO)", notes="DEMO MRV plan",
        measurements=[MeasurementIn(code="TILL", name="Tillage practice", category="TILLAGE", value_type="CHOICE",
                                    allowed_values=["CONVENTIONAL", "REDUCED", "NO_TILL"], level="FARM"),
                      MeasurementIn(code="RESIDUE", name="Crop residue retained", category="RESIDUE", value_type="BOOLEAN", level="FARM"),
                      MeasurementIn(code="N_APPL", name="Nitrogen applied", category="FERTILIZER", value_type="NUMBER", unit="kg N/ha",
                                    level="FARM", required=False)]))
    mrv_service.submit_plan(db, mrv_ctx, mrv, plan.id, "DEMO: plan ready")
    mrv_service.approve_plan(db, qa_ctx, qa, plan.id, "DEMO: approved; sampling requirements are not configured by the DEMO methodology", True)
    # the DEMO crediting period is 2026-06-01 .. 2036-05-31 (demo_projects)
    mp = mrv_service.create_period(db, mrv_ctx, mrv, PeriodIn(project_id=p.id, name="Monitoring period 1 (DEMO)", purpose="MONITORING",
                                                              start_date=date(2026, 6, 1), end_date=date(2027, 5, 31)))
    for action in ("plan", "start", "open-collection"):
        mrv_service.period_action(db, mrv_ctx, mrv, mp.id, action, f"DEMO: {action}")

    farms = [pf.farm_id for pf in project_repo.project_farms(db, p.id, active_only=True)]
    groups = [farms[:1], farms[1:]] if len(farms) > 1 else [farms]
    strata = []
    for i, (code, soil, ids) in enumerate(zip(("S1", "S2"), ("Vertisol (DEMO)", "Inceptisol (DEMO)"), groups, strict=False)):
        s = sampling_service.create_stratum(db, mrv_ctx, mrv, p.id, StratumIn(
            code=code, name=f"DEMO stratum {i + 1}", farm_ids=ids, description="DEMO stratification by soil type",
            characteristics=[CharacteristicIn(characteristic="SOIL_TYPE", value=soil), CharacteristicIn(characteristic="CROP",
                                                                                                        value="Grapes / onion")]))
        strata.append(sampling_service.approve_stratum(db, gis_ctx, gis, s.id, "DEMO: stratum geometry checked"))
    d = sampling_service.create_design(db, mrv_ctx, mrv, DesignIn(
        monitoring_period_id=mp.id, code="SOIL-1", name="DEMO soil sampling design", statistical_design="STRATIFIED_RANDOM",
        depth_top_cm=Decimal("0"), depth_bottom_cm=Decimal("30"), min_distance_m=Decimal("15"), random_seed=2026,
        sampling_method="Soil auger, composite of 5 cores (DEMO)", notes="DEMO: sample counts configured by the project, not by an area rule",
        allocations=[AllocationIn(stratum_id=s.id, sample_count=3) for s in strata]))
    dv = sampling_service.design_versions(db, d.id)[0]
    sampling_service.approve_design_version(db, gis_ctx, gis, d.id, dv.id, "DEMO: design approved")
    points = sampling_service.generate_points(db, mrv_ctx, mrv, d.id)
    sampling_service.bulk_assign(db, sup_ctx, sup, [x.id for x in points], col.user_id, date(2026, 9, 15), "DEMO: collect 0-30 cm")

    collected = 0
    for n, sp in enumerate(points[:3]):
        fc = sampling_service.start_collection(db, col_ctx, col, sp.id)
        sampling_service.update_collection(db, col_ctx, col, fc.id, CollectionUpdate(
            collected_at=datetime(2026, 9, 15, 9 + n, 0, tzinfo=timezone.utc), gps_latitude=float(sp.latitude), gps_longitude=float(sp.longitude),
            gps_accuracy_m=Decimal("4"), actual_depth_top_cm=sp.planned_depth_top_cm, actual_depth_bottom_cm=sp.planned_depth_bottom_cm,
            sample_quantity=Decimal("0.5"), sample_unit="kg", observations="DEMO: dry soil, residue present",
            checklist=dict.fromkeys(field_rules.checklist_keys(field_rules.of_design(dv)), True)))
        mrv_service.add_evidence(db, col_ctx, col, project_id=p.id, entity_type="FIELD_COLLECTION", entity_id=fc.id, evidence_type="FIELD_PHOTO",
                                 description="DEMO placeholder image (not a real photo)", latitude=float(sp.latitude),
                                 longitude=float(sp.longitude), captured_at=None, filename="demo-photo.png", data=DEMO_PNG)
        sampling_service.submit_collection(db, col_ctx, col, fc.id)
        if n < 2:
            sampling_service.review_collection(db, sup_ctx, sup, fc.id, "ACCEPTED", "DEMO: sample accepted")
        collected += 1

    till = next(m for m in mrv_service.measurements(db, plan.id) if m.code == "TILL")
    residue = next(m for m in mrv_service.measurements(db, plan.id) if m.code == "RESIDUE")
    for f in farms:
        for m, value in ((till, "REDUCED"), (residue, True)):
            mrv_service.add_monitoring_record(db, col_ctx, col, MonitoringRecordIn(
                monitoring_period_id=mp.id, measurement_id=m.id, farm_id=f, value=value, observed_on=date(2026, 9, 15),
                measurement_phase="PROJECT", source="FIELD_OBSERVATION", notes="DEMO observation"))
    mrv_service.create_dataset(db, mrv_ctx, mrv, DatasetIn(monitoring_period_id=mp.id, notes="DEMO dataset (collection in progress)"))
    return {"plans": 1, "points": len(points), "collections": collected}
