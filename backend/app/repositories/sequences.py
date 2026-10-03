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
             "credit_issuance": ("seq_credit_issuance_code", "ISS"), "credit_batch": ("seq_credit_batch_code", "CB"),
             "credit_entry": ("seq_credit_entry_code", "LEDG"), "credit_opening": ("seq_credit_opening_code", "OPN"),
             "credit_reservation": ("seq_credit_reservation_code", "RSV"), "credit_transfer": ("seq_credit_transfer_code", "TRF"),
             "credit_retirement": ("seq_credit_retirement_code", "RET"), "credit_reversal": ("seq_credit_reversal_code", "REV"),
             "listing": ("seq_listing_code", "LST"), "order": ("seq_order_code", "ORD"), "payment": ("seq_payment_code", "PAY"),
             "refund": ("seq_refund_code", "RFD"),
             "revenue": ("seq_revenue_code", "RVN"), "revenue_share": ("seq_revenue_share_code", "RSH"),
             "allocation": ("seq_allocation_code", "FAL"), "cost": ("seq_cost_code", "PCS"), "settlement": ("seq_settlement_code", "SET"),
             "payout": ("seq_payout_code", "PYT"), "adjustment": ("seq_adjustment_code", "ADJ")}


def next_code(db: Session, kind: str, year: int) -> str:
    sequence, prefix = SEQUENCES[kind]
    n = db.execute(text(f"SELECT NEXT VALUE FOR dbo.{sequence}")).scalar_one()
    return f"{prefix}-{year}-{int(n):06d}"
