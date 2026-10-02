"""DEMO farmers and farms (spec §43: 5 farmers, 10 farms), created through the real services so every
record passes validation, workflow guards and audit exactly like live data. Everything is environment=DEMO
because it belongs to DEMO organizations. Identity and bank numbers are obviously fake (DEMO…).
"""
from datetime import date
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.context import RequestContext
from app.models import Farm, Farmer, Organization, User
from app.schemas.farmers import BankAccountIn, ConsentIn, FarmerCreate
from app.schemas.farms import CropHistoryIn, FarmCreate, LandHistoryIn, OwnershipIn, PracticeHistoryIn
from app.security.principal import Principal, load_principal
from app.seed.accounts import DEMO_DOMAIN
from app.services import farm_service, farmer_service

PDF = b"%PDF-1.4\n% DEMO placeholder document - not a real record\n%%EOF\n"
BASE_LON, BASE_LAT = 73.80, 20.00   # Nashik district, Maharashtra (illustrative)

FARMERS: list[tuple[str, str, Literal["FEMALE", "MALE"]]] = [
    ("Asha Patil (DEMO)", "Pimpalgaon", "FEMALE"),
    ("Ravi Jadhav (DEMO)", "Ozar", "MALE"),
    ("Sunita Pawar (DEMO)", "Niphad", "FEMALE"),
    ("Mahesh Shinde (DEMO)", "Lasalgaon", "MALE"),
    ("Kavita More (DEMO)", "Sinnar", "FEMALE"),
]


def _actor(db: Session, local: str) -> tuple[Principal, RequestContext]:
    user = db.scalars(select(User).where(User.email == f"{local}@{DEMO_DOMAIN}")).one()
    return load_principal(db, user, None), RequestContext(request_id=f"seed-demo-{local}", user_id=user.id)


def _square(i: int, size: float = 0.0012) -> dict:
    lon, lat = BASE_LON + (i % 5) * 0.004, BASE_LAT + (i // 5) * 0.004
    return {"type": "Polygon", "coordinates": [[[lon, lat], [lon + size, lat], [lon + size, lat + size * 0.9],
                                                 [lon, lat + size * 0.9], [lon, lat]]]}


def seed_demo_farms(db: Session) -> dict[str, int]:
    org = db.scalars(select(Organization).where(Organization.code == "DEMO-DEV-A")).one()
    if db.scalars(select(Farmer).where(Farmer.organization_id == org.id)).first():
        return {"farmers": 0, "farms": 0}
    pm, pm_ctx = _actor(db, "pm")
    qa, qa_ctx = _actor(db, "qa")
    agent, agent_ctx = _actor(db, "collector")
    gis, gis_ctx = _actor(db, "gis")
    farmer_user = db.scalars(select(User).where(User.email == f"farmer@{DEMO_DOMAIN}")).one()

    farmers: list[Farmer] = []
    for n, (name, village, gender) in enumerate(FARMERS, start=1):
        f = farmer_service.create_farmer(db, pm_ctx, pm, FarmerCreate(
            organization_id=org.id, full_name=name, gender=gender, preferred_language="mr", village=village, district="Nashik",
            state="Maharashtra", country="IN", primary_phone=f"+91 90000 0000{n}"))
        farmer_service.change_status(db, pm_ctx, pm, f.id, "REGISTERED", "DEMO onboarding")
        kyc = farmer_service.upload_document(db, pm_ctx, pm, f.id, "KYC_ID", "DEMO identity document", "kyc.pdf", PDF)
        farmer_service.submit_kyc(db, pm_ctx, pm, f.id, "NATIONAL_ID", f"DEMO{n:08d}", kyc)
        farmer_service.decide_kyc(db, qa_ctx, qa, f.id, "VERIFIED", "DEMO: identity document checked", False)
        farmer_service.grant_consent(db, pm_ctx, pm, f.id, ConsentIn(consent_type="DATA_PROCESSING", consent_text_version="DEMO-DPC-1",
                                                                     language="mr", capture_method="PAPER_SIGNED"))
        farmer_service.change_status(db, pm_ctx, pm, f.id, "ACTIVE", "DEMO onboarding complete")
        farmer_service.add_bank_account(db, pm_ctx, pm, f.id, BankAccountIn(
            account_holder_name=name, bank_name="DEMO Cooperative Bank", routing_code="DEMO0000001",
            account_number=f"DEMO{n:010d}"))
        if n == 1:
            farmer_service.link_user(db, pm_ctx, pm, f.id, farmer_user.id)
        farmers.append(f)

    farms: list[Farm] = []
    for i in range(10):
        f = farmers[i // 2]
        leased = i % 2 == 1
        geo = _square(8) if i == 9 else _square(i)  # farm 10 deliberately overlaps farm 9 → OPEN overlap flag
        if i == 9:
            geo["coordinates"][0] = [[x + 0.0005, y] for x, y in geo["coordinates"][0]]
        farm = farm_service.create_farm(db, agent_ctx, agent, FarmCreate(
            farmer_id=f.id, name=f"{f.village} plot {i % 2 + 1} (DEMO)", village=f.village, district="Nashik", state="Maharashtra",
            country="IN", land_tenure="LEASED" if leased else "OWNED"))
        farm_service.save_boundary(db, agent_ctx, agent, farm.id, geo, None, "DRAWN")
        own = farm_service.add_ownership(db, agent_ctx, agent, farm.id, OwnershipIn(
            owner_type="INDIVIDUAL" if leased else "FARMER", owner_farmer_id=None if leased else f.id,
            owner_name="Landowner (DEMO)" if leased else None, operator_relationship="LESSEE" if leased else "OWNER",
            title_reference=f"DEMO-7/12-{100 + i}", valid_from=date(2018, 6, 1)))
        for year in range(2019, 2024):
            farm_service.history_action(db, agent_ctx, agent, farm.id, "land", "add", data=LandHistoryIn(year=year, land_use="CROPLAND"))
        for year, crop in ((2021, "Soybean"), (2022, "Wheat"), (2023, "Soybean")):
            farm_service.history_action(db, agent_ctx, agent, farm.id, "crop", "add", data=CropHistoryIn(
                year=year, season="Kharif" if crop == "Soybean" else "Rabi", crop_name=crop, irrigation="RAINFED",
                residue_management="BURNED" if year < 2023 else "INCORPORATED"))
        farm_service.history_action(db, agent_ctx, agent, farm.id, "practice", "add", data=PracticeHistoryIn(
            year=2023, practice_phase="HISTORICAL", practice_category="TILLAGE", practice_type="Conventional ploughing"))
        farm_service.history_action(db, agent_ctx, agent, farm.id, "practice", "add", data=PracticeHistoryIn(
            year=2026, practice_phase="PROPOSED", practice_category="TILLAGE", practice_type="Reduced tillage",
            implementation_status="PLANNED", expected_change="Reduce soil disturbance; retain residue"))
        if i < 9:
            farm_service.submit(db, agent_ctx, agent, farm.id, "DEMO: ready for GIS review")
        if i < 6 or i == 8:
            farm_service.start_review(db, gis_ctx, gis, farm.id, "DEMO review")
        if i < 6:
            farm_service.review_ownership(db, gis_ctx, gis, farm.id, own.id, "VERIFIED", "DEMO: land record extract matches")
            farm_service.verify(db, gis_ctx, gis, farm.id, "DEMO: boundary and tenure confirmed")
        farms.append(farm)
    return {"farmers": len(farmers), "farms": len(farms)}
