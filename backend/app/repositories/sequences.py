"""Human-readable business codes from SQL Server sequences (safe under concurrency)."""
from sqlalchemy import text
from sqlalchemy.orm import Session

SEQUENCES = {"farmer": ("seq_farmer_code", "FRM"), "farm": ("seq_farm_code", "FARM"), "agreement": ("seq_agreement_number", "AGR"),
             "project": ("seq_project_code", "PRJ"),
             "sampling_point": ("seq_sampling_point_code", "SP"),
             "field_collection": ("seq_field_collection_code", "FIELD"),
             "lab_sample": ("seq_sample_code", "SMP"), "lab_shipment": ("seq_shipment_code", "SHP"), "lab_test": ("seq_lab_test_code", "LT"),
             "calculation_run": ("seq_calculation_run_code", "CALC"),
             "calculation_finding": ("seq_calculation_finding_code", "CFND"), "calculation_report": ("seq_calculation_report_code", "CRPT"),
             "calculation_readiness": ("seq_calculation_readiness_code", "RDY"),
             "verification_assignment": ("seq_verification_assignment_code", "VAS"),
             "verification_submission": ("seq_verification_submission_code", "VSUB"),
             "verification_finding": ("seq_verification_finding_code", "VFND"),
             "corrective_action": ("seq_corrective_action_code", "CAR"),
             "verification_decision": ("seq_verification_decision_code", "VDEC"),
             "registry_registration": ("seq_registry_registration_code", "RREG"),
             "registry_submission": ("seq_registry_submission_code", "RSUB"),
             "credit_issuance": ("seq_credit_issuance_code", "ISS"), "credit_batch": ("seq_credit_batch_code", "CB")}


def next_code(db: Session, kind: str, year: int) -> str:
    sequence, prefix = SEQUENCES[kind]
    n = db.execute(text(f"SELECT NEXT VALUE FOR dbo.{sequence}")).scalar_one()
    return f"{prefix}-{year}-{int(n):06d}"
