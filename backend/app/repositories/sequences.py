"""Human-readable business codes from SQL Server sequences (safe under concurrency)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

SEQUENCES = {"farmer": ("seq_farmer_code", "FRM"), "farm": ("seq_farm_code", "FARM"), "agreement": ("seq_agreement_number", "AGR"),
             "project": ("seq_project_code", "PRJ"),
             "sampling_point": ("seq_sampling_point_code", "SP"),
             "field_collection": ("seq_field_collection_code", "FIELD"),
             "lab_sample": ("seq_sample_code", "SMP"), "lab_shipment": ("seq_shipment_code", "SHP"), "lab_test": ("seq_lab_test_code", "LT")}


def next_code(db: Session, kind: str, year: int) -> str:
    sequence, prefix = SEQUENCES[kind]
    n = db.execute(text(f"SELECT NEXT VALUE FOR dbo.{sequence}")).scalar_one()
    return f"{prefix}-{year}-{int(n):06d}"
