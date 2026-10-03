"""Phase 12B D30 — re-encrypt field-level encrypted values after a DATA_ENCRYPTION_KEY rotation.

Rotation runbook (docs/runtime-hardening.md): generate a new Fernet key in the secret store, make it DATA_ENCRYPTION_KEY and move the
old key to DATA_ENCRYPTION_PREVIOUS_KEYS, restart, run `manage.py rotate-data-key`, then remove the old key. Values are decrypted with
any configured key and re-encrypted with the current one; plaintext never leaves this function and is never logged. Each batch is its
own transaction; a value that no configured key can decrypt is counted and left untouched. `updated_at` is preserved (a key rotation
is not a business change). One SECURITY event records the counts.
"""
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.audit.service import security_event
from app.core.context import RequestContext
from app.models import FarmerBankAccount
from app.security import crypto


def reencrypt_bank_accounts(db: Session, *, dry_run: bool = False, batch_size: int = 500) -> dict[str, Any]:
    counts = {"rows": 0, "rotated": 0, "already_current": 0, "undecryptable": 0}
    last = None
    while True:
        stmt = select(FarmerBankAccount.id, FarmerBankAccount.account_number_enc).order_by(FarmerBankAccount.id).limit(batch_size)
        if last is not None:
            stmt = stmt.where(FarmerBankAccount.id > last)
        rows = db.execute(stmt).all()
        if not rows:
            break
        for rid, token in rows:
            counts["rows"] += 1
            if not crypto.needs_rotation(token):
                counts["already_current"] += 1
                continue
            try:
                new = crypto.rotate(token)
            except ValueError:
                counts["undecryptable"] += 1
                continue
            counts["rotated"] += 1
            if not dry_run:
                db.execute(update(FarmerBankAccount).where(FarmerBankAccount.id == rid)
                           .values(account_number_enc=new, updated_at=FarmerBankAccount.updated_at)
                           .execution_options(synchronize_session=False))
        if not dry_run:
            db.commit()
        last = rows[-1][0]
    if not dry_run:
        security_event(db, RequestContext.system("rotate-data-key"), "DATA_ENCRYPTION_KEY_ROTATED",
                       "WARNING" if counts["undecryptable"] else "INFO", details=counts)
        db.commit()
    return counts
