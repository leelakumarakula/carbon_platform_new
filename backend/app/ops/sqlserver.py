"""SQL Server backup / restore helpers (Phase 12B-III, D25–D27). Every destructive step is guarded:

- database names must be plain identifiers (no injection through names);
- restore / drop only ever target a SCRATCH database whose name ends with `_restoretest` and is not the configured application
  database, not a system database and not referenced by DATABASE_URL — a drill can never restore over a live database (D27);
- drills are refused when APP_ENV=production (run them on a separate, non-production restore host);
- production backups must be encrypted (BACKUP_ENCRYPTION_CERT) and off-host (BACKUP_URL) (D26).

Statements run on a raw DBAPI cursor whose result sets are drained: SQL Server streams progress messages as result sets and an
undrained BACKUP / RESTORE is cut short by the driver.
"""
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from app.core.config import get_settings
from app.ops.disk import ensure_headroom

NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]{0,99}$")
SCRATCH_SUFFIX = "_restoretest"
SYSTEM_DATABASES = frozenset({"master", "model", "msdb", "tempdb"})
BACKUP_TYPES = {"full": "D", "diff": "I", "log": "L"}


class UnsafeTarget(RuntimeError):
    """A command was pointed at a database it must not touch."""


def master_engine() -> Engine:
    return create_engine(get_settings().database_url("master"), isolation_level="AUTOCOMMIT")


def database_engine(name: str) -> Engine:
    return create_engine(get_settings().database_url(check_name(name)), isolation_level="AUTOCOMMIT")


def check_name(name: str) -> str:
    if not NAME.fullmatch(name or ""):
        raise UnsafeTarget(f"{name!r} is not a plain database name")
    return name


def protected_names() -> set[str]:
    s = get_settings()
    names = {s.SQL_SERVER_DATABASE.lower(), *SYSTEM_DATABASES}
    if s.DATABASE_URL:
        db = urlsplit(s.DATABASE_URL).path.lstrip("/")
        if db:
            names.add(db.lower())
    return names


def check_scratch(name: str) -> str:
    """The only database name a drill may create, overwrite or drop."""
    check_name(name)
    if get_settings().is_production:
        raise UnsafeTarget("Restore drills are refused in production: run them on a separate, non-production restore host.")
    if not name.endswith(SCRATCH_SUFFIX) or name.lower() in protected_names():
        raise UnsafeTarget(f"{name!r} is not a scratch database (names must end with {SCRATCH_SUFFIX!r} and differ from the "
                           "application database)")
    return name


def run(engine: Engine, sql: str) -> None:
    raw = engine.raw_connection()
    try:
        cur = raw.cursor()
        cur.execute(sql)
        while cur.nextset():
            pass
        cur.close()
    finally:
        raw.close()


def exists(engine: Engine, name: str) -> bool:
    with engine.connect() as c:
        return c.execute(text("SELECT DB_ID(:n)"), {"n": check_name(name)}).scalar() is not None


def used_mb(engine: Engine, name: str) -> int:
    """Pages in use by the database's files (an upper bound for an uncompressed backup)."""
    with engine.connect() as c:
        pages = c.execute(text("SELECT SUM(CAST(size AS bigint)) FROM sys.master_files WHERE database_id = DB_ID(:n)"),
                          {"n": check_name(name)}).scalar()
    return int((pages or 0) * 8 // 1024)


def server_free_mb(engine: Engine, path: str) -> int:
    """Free space of the volume holding `path`, as SQL Server sees it (the service account's view; works for a remote server too)."""
    drive = path[:1].upper() if len(path) > 1 and path[1] == ":" else None
    with engine.connect() as c:
        if drive:
            for letter, mb in c.execute(text("EXEC master.sys.xp_fixeddrives")).all():
                if str(letter).upper() == drive:
                    return int(mb)
        mb = c.execute(text("SELECT MIN(available_bytes) / 1048576 FROM sys.master_files f "
                            "CROSS APPLY sys.dm_os_volume_stats(f.database_id, f.file_id) WHERE f.database_id = DB_ID('master')")).scalar()
    return int(mb or 0)


def ensure_server_headroom(engine: Engine, path: str, needed_mb: int) -> int:
    return ensure_headroom(path, needed_mb, free=server_free_mb(engine, path))


def default_backup_dir(engine: Engine) -> str:
    with engine.connect() as c:
        return str(c.execute(text("SELECT CAST(SERVERPROPERTY('InstanceDefaultBackupPath') AS nvarchar(400))")).scalar()).rstrip("\\/")


@dataclass
class BackupResult:
    database: str
    kind: str
    destination: str
    encrypted: bool
    copy_only: bool
    seconds: float
    verified: bool = False
    size_mb: float | None = None
    notes: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {k: getattr(self, k) for k in ("database", "kind", "destination", "encrypted", "copy_only", "seconds", "verified", "size_mb",
                                              "notes")}


def backup_sql(database: str, kind: str, destination: str, *, copy_only: bool, certificate: str | None) -> str:
    check_name(database)
    if kind not in BACKUP_TYPES:
        raise ValueError(f"backup type must be one of {sorted(BACKUP_TYPES)}")
    target = f"URL = N'{destination}'" if destination.startswith("s3://") else f"DISK = N'{destination}'"
    if "'" in destination:
        raise UnsafeTarget("backup destination must not contain quotes")
    opts = ["CHECKSUM", "COMPRESSION", "FORMAT", "INIT"]
    if kind == "diff":
        opts.insert(0, "DIFFERENTIAL")
    if copy_only:
        opts.append("COPY_ONLY")
    if certificate:
        opts.append(f"ENCRYPTION (ALGORITHM = AES_256, SERVER CERTIFICATE = [{check_name(certificate)}])")
    verb = "BACKUP LOG" if kind == "log" else "BACKUP DATABASE"
    return f"{verb} [{database}] TO {target} WITH {', '.join(opts)}"


def backup(database: str, kind: str = "full", *, destination: str | None = None, copy_only: bool = False,
           verify: bool = True) -> BackupResult:
    """Back up `database`. Production: encrypted (BACKUP_ENCRYPTION_CERT) and off-host (BACKUP_URL) or refused (D26)."""
    s = get_settings()
    eng = master_engine()
    try:
        if not exists(eng, database):
            raise UnsafeTarget(f"database {database!r} does not exist")
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        if destination is None:
            if s.BACKUP_URL:
                destination = f"{s.BACKUP_URL.rstrip('/')}/{database}/{kind}/{database}_{kind}_{stamp}.bak"
            else:
                destination = f"{default_backup_dir(eng)}\\{database}_{kind}_{stamp}.bak"
        off_host = destination.startswith("s3://")
        if s.is_production and not (s.BACKUP_ENCRYPTION_CERT and off_host):
            raise UnsafeTarget("Production backups must be encrypted (BACKUP_ENCRYPTION_CERT) and off-host (BACKUP_URL, s3://) (D26).")
        if not off_host:                                          # a local file: keep the disk from being exhausted
            ensure_server_headroom(eng, destination, used_mb(eng, database))
        t = time.monotonic()
        run(eng, backup_sql(database, kind, destination, copy_only=copy_only, certificate=s.BACKUP_ENCRYPTION_CERT))
        res = BackupResult(database, kind, destination, bool(s.BACKUP_ENCRYPTION_CERT), copy_only, round(time.monotonic() - t, 2))
        if not res.encrypted:
            res.notes.append("UNENCRYPTED: acceptable for local drills only; production refuses (D26)")
        with eng.connect() as c:
            size = c.execute(text("SELECT TOP 1 compressed_backup_size / 1048576.0 FROM msdb.dbo.backupset b "
                                  "JOIN msdb.dbo.backupmediafamily f ON f.media_set_id = b.media_set_id "
                                  "WHERE b.database_name = :d AND f.physical_device_name = :p ORDER BY b.backup_finish_date DESC"),
                             {"d": database, "p": destination}).scalar()
        res.size_mb = round(float(size), 1) if size is not None else None
        if verify:
            verify_backup(eng, destination)
            res.verified = True
        return res
    finally:
        eng.dispose()


def verify_backup(eng: Engine, destination: str) -> None:
    src = f"URL = N'{destination}'" if destination.startswith("s3://") else f"DISK = N'{destination}'"
    run(eng, f"RESTORE VERIFYONLY FROM {src} WITH CHECKSUM")


def restore_to_scratch(eng: Engine, destination: str, scratch: str) -> None:
    """Restore a backup into the scratch database only (never over another database)."""
    check_scratch(scratch)
    src = f"URL = N'{destination}'" if destination.startswith("s3://") else f"DISK = N'{destination}'"
    with eng.connect() as c:
        files = c.execute(text(f"RESTORE FILELISTONLY FROM {src}")).all()
        data_dir = str(c.execute(text("SELECT CAST(SERVERPROPERTY('InstanceDefaultDataPath') AS nvarchar(400))")).scalar()).rstrip("\\/")
    moves = []
    for i, f in enumerate(files):
        ext = "ldf" if str(f.Type).upper() == "L" else "mdf" if i == 0 else "ndf"
        moves.append(f"MOVE N'{f.LogicalName}' TO N'{data_dir}\\{scratch}_{i}.{ext}'")
    replace = ", REPLACE" if exists(eng, scratch) else ""
    run(eng, f"RESTORE DATABASE [{scratch}] FROM {src} WITH {', '.join(moves)}, CHECKSUM, RECOVERY{replace}")


def drop_scratch(eng: Engine, scratch: str) -> None:
    check_scratch(scratch)
    if exists(eng, scratch):
        run(eng, f"ALTER DATABASE [{scratch}] SET SINGLE_USER WITH ROLLBACK IMMEDIATE")
        run(eng, f"DROP DATABASE [{scratch}]")


def delete_backup_file(eng: Engine, path: str) -> None:
    """Removes a LOCAL drill backup file written by SQL Server (the service account owns it)."""
    if path.startswith("s3://") or "'" in path or not path.lower().endswith(".bak"):
        raise UnsafeTarget("only local .bak files created by a drill are deleted here")
    run(eng, f"EXEC master.sys.xp_delete_files N'{path}'")


def backup_freshness(eng: Engine, database: str) -> dict[str, float | None]:
    """Seconds since the last successful FULL / DIFF / LOG backup of `database` (None = never / not visible)."""
    out: dict[str, float | None] = dict.fromkeys(BACKUP_TYPES)
    with eng.connect() as c:
        rows = c.execute(text("SELECT type, DATEDIFF_BIG(second, MAX(backup_finish_date), GETDATE()) FROM msdb.dbo.backupset "
                              "WHERE database_name = :d AND is_copy_only = 0 GROUP BY type"), {"d": check_name(database)}).all()
    for t, age in rows:
        for k, code in BACKUP_TYPES.items():
            if t == code:
                out[k] = float(age)
    return out
