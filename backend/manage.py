"""Developer / operations CLI.

  python manage.py create-db          create the SQL Server database (READ_COMMITTED_SNAPSHOT on) if missing
  python manage.py migrate            alembic upgrade head
  python manage.py seed-reference     sync permissions, system roles, platform organization
  python manage.py bootstrap-admin    first Platform Admin from BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD
  python manage.py seed-demo          DEMO organizations + one user per role (password from DEMO_USER_PASSWORD)
  python manage.py setup              create-db + migrate + seed-reference
  python manage.py jobs-recover       one background-job recovery pass (requeue stale / due jobs, republish unpublished ones)
  python manage.py rotate-data-key [--dry-run]
                                      re-encrypt stored bank account numbers with DATA_ENCRYPTION_KEY (old keys listed in
                                      DATA_ENCRYPTION_PREVIOUS_KEYS); run after a key rotation, then remove the old keys
  python manage.py verify-restore --database NAME [--compare-with NAME] [--objects N] [--checkdb] [--report FILE]
                                      read-only checks of a restored database (schema, triggers, ledger, settlements, scoping, ...)
  python manage.py restore-drill --source NAME [--scratch NAME_restoretest] [--from-backup PATH] [--keep-backup] [--objects N]
                                      backup -> verify -> restore into a scratch database -> verify-restore -> drop (never production)
  python manage.py backup --database NAME --type full|diff|log [--to PATH_OR_S3_URL] [--copy-only] [--no-verify]
                                      SQL Server backup WITH CHECKSUM, COMPRESSION; production: encrypted + off-host or refused
  python manage.py schema-manifest --database NAME
                                      regenerate app/ops/schema_manifest.json from a database at the migration head
  python manage.py storage-migrate [--dry-run]
                                      copy every document object from LOCAL_STORAGE_ROOT into the configured object store
                                      (STORAGE_BACKEND=s3), verifying SHA-256; local originals are never deleted
"""
import argparse
import os
import re
import sys
from collections.abc import Callable

from sqlalchemy import create_engine, text


def create_db() -> None:
    from app.core.config import get_settings
    s = get_settings()
    name = s.SQL_SERVER_DATABASE
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,99}", name):
        sys.exit(f"Refusing unsafe database name: {name!r}")
    engine = create_engine(s.database_url("master"), isolation_level="AUTOCOMMIT")
    with engine.connect() as c:
        if c.scalar(text("SELECT DB_ID(:n)"), {"n": name}) is None:
            c.execute(text(f"CREATE DATABASE [{name}]"))
            print(f"Created database {name}")
        c.execute(text(f"ALTER DATABASE [{name}] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE"))
        c.execute(text(f"ALTER DATABASE [{name}] SET ALLOW_SNAPSHOT_ISOLATION ON"))
        if name.endswith("_test"):  # disposable test database: no point-in-time recovery, keep the log small
            c.execute(text(f"ALTER DATABASE [{name}] SET RECOVERY SIMPLE"))
    engine.dispose()
    print(f"Database {name} ready")


def migrate() -> None:
    from alembic import command
    from alembic.config import Config
    command.upgrade(Config(os.path.join(os.path.dirname(__file__), "alembic.ini")), "head")


def seed_reference() -> None:
    from app.core.database import get_session_factory
    from app.seed.reference import sync_reference
    with get_session_factory()() as db:
        print("reference data:", sync_reference(db))


def bootstrap_admin() -> None:
    from app.core.config import get_settings
    from app.core.database import get_session_factory
    from app.seed.accounts import bootstrap_admin as boot
    st = get_settings()
    email, pw = st.BOOTSTRAP_ADMIN_EMAIL, st.BOOTSTRAP_ADMIN_PASSWORD
    if not email or not pw:
        sys.exit("Set BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD (environment or backend/.env).")
    with get_session_factory()() as db:
        user, created = boot(db, email, pw, st.BOOTSTRAP_ADMIN_NAME)
        note = "(must change password at first sign-in)" if created else ""
        print("Created" if created else "Already exists:", user.email, note)


def seed_demo() -> None:
    from app.core.config import get_settings
    from app.core.database import get_session_factory
    from app.seed.accounts import DEMO_DOMAIN
    from app.seed.accounts import seed_demo as demo
    pw = get_settings().DEMO_USER_PASSWORD
    if not pw:
        sys.exit("Set DEMO_USER_PASSWORD (environment or backend/.env).")
    from app.seed.demo_farms import seed_demo_farms
    from app.seed.demo_lab import seed_demo_lab
    from app.seed.demo_methodologies import seed_demo_methodologies
    from app.seed.demo_mrv import seed_demo_mrv
    from app.seed.demo_projects import seed_demo_projects
    with get_session_factory()() as db:
        print("demo data:", demo(db, pw), f"- accounts are <role>@{DEMO_DOMAIN}, environment=DEMO")
        print("demo farmers & farms:", seed_demo_farms(db))
        print("demo projects:", seed_demo_projects(db))
        print("demo methodologies:", seed_demo_methodologies(db))
        print("demo MRV (no lab results, calculations or credits):", seed_demo_mrv(db))
        print("demo laboratory (manual DEMO flow, DEMO placeholder values; no calculations or credits):", seed_demo_lab(db))


def jobs_recover() -> None:
    """Runbook (Phase 12A): run one recovery pass — requeue stale claims, recover lost runs, requeue due retries and republish QUEUED
    jobs whose publication failed (e.g. after a Redis outage). Executes no job and performs no business work itself."""
    from app.core.database import get_session_factory
    from app.workers import job_service
    with get_session_factory()() as db:
        print("job recovery:", job_service.recover(db))


def storage_migrate(dry_run: bool = False) -> None:
    """Runbook (Phase 12B D9): local -> MinIO. Requires STORAGE_BACKEND=s3 and the OBJECT_STORAGE_* settings; idempotent (re-run
    after an interruption); exits non-zero if any object is missing, mismatched or could not be written."""
    from app.core.database import get_session_factory
    from app.integrations.storage import LocalFileStorage, get_storage, local_root
    from app.services.storage_migration import migrate_local_to
    target = get_storage()
    if target.name != "s3":
        sys.exit("storage-migrate needs STORAGE_BACKEND=s3 and the OBJECT_STORAGE_* settings (the target object store).")
    problems = target.health()
    if problems:
        sys.exit("Object store is not ready: " + "; ".join(problems))
    with get_session_factory()() as db:
        rep = migrate_local_to(db, LocalFileStorage(local_root()), target, dry_run=dry_run)
    print("storage migration" + (" (dry run)" if dry_run else "") + ":", rep.as_dict())
    if not rep.ok:
        sys.exit(1)


def rotate_data_key(dry_run: bool = False) -> None:
    """Runbook (Phase 12B D30): idempotent, batched; values already on the current key are skipped. Exit code 1 if any value
    cannot be decrypted with any configured key (nothing is overwritten in that case)."""
    from app.core.database import get_session_factory
    from app.services.key_rotation import reencrypt_bank_accounts
    with get_session_factory()() as db:
        rep = reencrypt_bank_accounts(db, dry_run=dry_run)
    print("data key rotation" + (" (dry run)" if dry_run else "") + ":", rep)
    if rep["undecryptable"]:
        sys.exit(1)


def _emit(result: dict, ok: bool, report_file: str | None = None) -> None:
    import json
    import logging
    text_out = json.dumps(result, indent=2, default=str)
    print(text_out)
    if report_file:
        with open(report_file, "w", encoding="utf-8") as f:
            f.write(text_out)
    logging.getLogger("app.ops").log(logging.INFO if ok else logging.ERROR, "operation result",
                                     extra={"fields": {"ok": ok, "operation": sys.argv[1] if len(sys.argv) > 1 else None}})
    if not ok:
        sys.exit(1)


def verify_restore_cmd(args: argparse.Namespace) -> None:
    """Runbook (Phase 12B-III D27): exit code 1 when any check fails; --report writes the JSON result for the drill record."""
    from app.ops.verify_restore import verify_restore
    if not args.database:
        sys.exit("verify-restore needs --database (the restored database to check; nothing is assumed)")
    rep = verify_restore(args.database, compare_with=args.compare_with, objects=args.objects, checkdb=args.checkdb)
    _emit(rep.as_dict(), rep.ok, args.report)


def restore_drill_cmd(args: argparse.Namespace) -> None:
    from app.ops.drill import restore_drill
    if not args.source:
        sys.exit("restore-drill needs --source (the database to back up and restore into a scratch copy)")
    out = restore_drill(args.source, args.scratch, from_backup=args.from_backup, keep_backup=args.keep_backup, objects=args.objects)
    _emit(out, bool(out.get("ok")), args.report)


def backup_cmd(args: argparse.Namespace) -> None:
    from app.ops.sqlserver import backup
    if not args.database or not args.type:
        sys.exit("backup needs --database and --type full|diff|log")
    res = backup(args.database, args.type, destination=args.to, copy_only=args.copy_only, verify=not args.no_verify)
    _emit(res.as_dict(), True, args.report)


def schema_manifest_cmd(args: argparse.Namespace) -> None:
    import json

    from app.ops.sqlserver import database_engine
    from app.ops.verify_restore import MANIFEST, build_manifest, code_head
    if not args.database:
        sys.exit("schema-manifest needs --database (a database at the migration head, e.g. the test database)")
    eng = database_engine(args.database)
    try:
        with eng.connect() as c:
            from sqlalchemy import text as _t
            version = c.execute(_t("SELECT version_num FROM dbo.alembic_version")).scalar()
            if version != code_head():
                sys.exit(f"{args.database} is at {version}, the code head is {code_head()}: migrate it first")
            manifest = {"head": version, **build_manifest(c)}
    finally:
        eng.dispose()
    MANIFEST.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {MANIFEST} ({len(manifest['tables'])} tables, {len(manifest['triggers'])} triggers)")


def setup() -> None:
    create_db()
    migrate()
    seed_reference()


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("command", choices=["backup", "bootstrap-admin", "create-db", "jobs-recover", "migrate", "restore-drill",
                                       "rotate-data-key", "schema-manifest", "seed-demo", "seed-reference", "setup", "storage-migrate",
                                       "verify-restore"])
    p.add_argument("--dry-run", action="store_true", help="storage-migrate / rotate-data-key: check and count, write nothing")
    p.add_argument("--database", help="verify-restore / backup / schema-manifest: the target database (always explicit)")
    p.add_argument("--compare-with", help="verify-restore: compare row counts with this source database")
    p.add_argument("--objects", type=int, default=0, help="verify-restore / restore-drill: verify N document objects in storage")
    p.add_argument("--checkdb", action="store_true", help="verify-restore: also run DBCC CHECKDB")
    p.add_argument("--report", help="write the JSON result to this file")
    p.add_argument("--source", help="restore-drill: database to back up")
    p.add_argument("--scratch", help="restore-drill: scratch database name (must end with _restoretest)")
    p.add_argument("--from-backup", help="restore-drill: restore this existing backup instead of taking one")
    p.add_argument("--keep-backup", action="store_true", help="restore-drill: keep the drill's backup file")
    p.add_argument("--type", choices=["full", "diff", "log"], help="backup: backup type")
    p.add_argument("--to", help="backup: destination file path or s3:// URL (default: BACKUP_URL, else the instance backup directory)")
    p.add_argument("--copy-only", action="store_true", help="backup: COPY_ONLY (does not affect the backup chain)")
    p.add_argument("--no-verify", action="store_true", help="backup: skip RESTORE VERIFYONLY")
    args = p.parse_args()
    cmds: dict[str, Callable[[], None]] = {
        "create-db": create_db, "migrate": migrate, "seed-reference": seed_reference, "bootstrap-admin": bootstrap_admin,
        "seed-demo": seed_demo, "setup": setup, "jobs-recover": jobs_recover, "storage-migrate": lambda: storage_migrate(args.dry_run),
        "rotate-data-key": lambda: rotate_data_key(args.dry_run), "verify-restore": lambda: verify_restore_cmd(args),
        "restore-drill": lambda: restore_drill_cmd(args), "backup": lambda: backup_cmd(args),
        "schema-manifest": lambda: schema_manifest_cmd(args)}
    cmds[args.command]()


if __name__ == "__main__":
    main()
