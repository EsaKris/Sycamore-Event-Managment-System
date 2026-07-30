"""
Database + media backups.

A backup is a single .tar.gz containing:
  - db.dump (Postgres, via pg_dump -Fc), db.sql (MySQL, via mysqldump),
    db.json (dumpdata fallback if the native dump tool isn't available —
    e.g. a shared host without mysqldump on PATH), or db.sqlite3 (SQLite,
    via the sqlite3 module's own backup() API — a consistent snapshot even
    if something is mid-write, unlike a raw file copy)
  - media/  — everything under MEDIA_ROOT (passport photos, church
    logos). A database-only backup would restore every Registration
    perfectly and every photo would come back broken, since the photo
    *files* were never in the database to begin with — only their paths.

Used by:
  - apps/dashboard/views.py:backup_download (Super Admin, on-demand)
  - apps/core/management/commands/backup_db.py (cron/automation)

Both call create_backup() so there's exactly one place this logic lives.
"""

import logging
import os
import sqlite3
import subprocess
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


class BackupError(Exception):
    """Raised when a backup could not be completed."""


@dataclass
class BackupResult:
    path: Path            # local .tar.gz path (always written, even if S3 upload was also requested)
    size_bytes: int
    uploaded_to_s3: bool
    s3_error: str = ''


def _dump_mysql(db, dest_dir: Path) -> Path:
    """
    Tries mysqldump first (fast, native SQL restore). Shared hosts like
    cPanel usually do have it available even without shell access to
    install anything else — but if it's missing or blocked, falls back to
    Django's own dumpdata (JSON fixture), which needs no external binary
    at all since it goes through the ORM.
    """
    dump_path = dest_dir / 'db.sql'
    cmd = [
        'mysqldump',
        '-h', db.get('HOST', 'localhost'),
        '-P', str(db.get('PORT', 3306)),
        '-u', db.get('USER', ''),
        f"-p{db.get('PASSWORD', '')}",
        '--single-transaction', '--skip-lock-tables', '--result-file', str(dump_path),
        db.get('NAME', ''),
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        return dump_path
    except FileNotFoundError:
        logger.warning("mysqldump not found on PATH — falling back to Django's dumpdata (JSON) instead.")
    except subprocess.CalledProcessError as exc:
        logger.warning("mysqldump failed (%s) — falling back to Django's dumpdata (JSON) instead.", exc.stderr.strip() or exc)
    return _dump_via_dumpdata(dest_dir)


def _dump_via_dumpdata(dest_dir: Path) -> Path:
    """
    Engine-agnostic fallback: Django's own dumpdata management command,
    which needs no external database-client binary at all — only used
    when a native dump tool (mysqldump/pg_dump) isn't available, since a
    JSON fixture is slower to restore on a large database than a native
    SQL/binary dump.
    """
    from django.core.management import call_command

    dump_path = dest_dir / 'db.json'
    with open(dump_path, 'w') as f:
        call_command('dumpdata', '--natural-foreign', '--natural-primary', stdout=f)
    return dump_path


def _dump_postgres(db, dest_dir: Path) -> Path:
    dump_path = dest_dir / 'db.dump'
    env = {**os.environ, 'PGPASSWORD': db.get('PASSWORD', '')}
    cmd = [
        'pg_dump', '-Fc',
        '-h', db.get('HOST', 'localhost'),
        '-p', str(db.get('PORT', 5432)),
        '-U', db.get('USER', ''),
        '-f', str(dump_path),
        db.get('NAME', ''),
    ]
    try:
        subprocess.run(cmd, env=env, check=True, capture_output=True, text=True)
    except FileNotFoundError:
        raise BackupError(
            "pg_dump isn't installed/on PATH on this server. Install the "
            "postgresql-client package (matching your Postgres server version)."
        )
    except subprocess.CalledProcessError as exc:
        raise BackupError(f"pg_dump failed: {exc.stderr.strip() or exc}")
    return dump_path


def _dump_sqlite(db, dest_dir: Path) -> Path:
    src_path = Path(db['NAME'])
    dest_path = dest_dir / 'db.sqlite3'
    # sqlite3's own backup API gives a consistent snapshot even if the app
    # is actively writing, unlike a plain shutil.copy of the .sqlite3 file.
    src_conn = sqlite3.connect(str(src_path))
    dest_conn = sqlite3.connect(str(dest_path))
    with dest_conn:
        src_conn.backup(dest_conn)
    src_conn.close()
    dest_conn.close()
    return dest_path


def _upload_to_s3(local_path: Path, filename: str) -> None:
    try:
        import boto3
    except ImportError:
        raise BackupError(
            "BACKUP_S3_BUCKET is set but boto3 isn't installed. "
            "Run: pip install boto3"
        )
    key = f"{settings.BACKUP_S3_PREFIX.rstrip('/')}/{filename}"
    boto3.client('s3').upload_file(str(local_path), settings.BACKUP_S3_BUCKET, key)


def _prune_old_backups(backup_dir: Path, keep: int) -> int:
    """Deletes local backups beyond the retention count, oldest first.
    Only prunes local disk — never touches anything already uploaded to S3,
    since that's the off-host copy specifically meant to survive this."""
    files = sorted(backup_dir.glob('sems-backup-*.tar.gz'), key=lambda p: p.stat().st_mtime, reverse=True)
    removed = 0
    for old in files[keep:]:
        old.unlink(missing_ok=True)
        removed += 1
    return removed


def create_backup() -> BackupResult:
    db = settings.DATABASES['default']
    engine = db['ENGINE']

    backup_dir = Path(settings.BACKUP_DIR)
    backup_dir.mkdir(parents=True, exist_ok=True)

    timestamp = timezone.now().strftime('%Y%m%d-%H%M%S')
    filename = f'sems-backup-{timestamp}.tar.gz'
    archive_path = backup_dir / filename

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        if 'postgresql' in engine:
            db_dump_path = _dump_postgres(db, tmp_dir)
        elif 'mysql' in engine:
            db_dump_path = _dump_mysql(db, tmp_dir)
        elif 'sqlite3' in engine:
            db_dump_path = _dump_sqlite(db, tmp_dir)
        else:
            raise BackupError(f"Unsupported database engine for backup: {engine}")

        with tarfile.open(archive_path, 'w:gz') as tar:
            tar.add(db_dump_path, arcname=db_dump_path.name)
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists():
                tar.add(media_root, arcname='media')

    uploaded = False
    s3_error = ''
    if settings.BACKUP_S3_BUCKET:
        try:
            _upload_to_s3(archive_path, filename)
            uploaded = True
        except Exception as exc:
            # An S3 failure should never lose the local backup that already
            # succeeded — log it and let the caller decide what to tell the user.
            logger.exception('Backup S3 upload failed')
            s3_error = str(exc)

    removed = _prune_old_backups(backup_dir, settings.BACKUP_RETENTION_COUNT)
    if removed:
        logger.info('Pruned %d old local backup(s)', removed)

    return BackupResult(
        path=archive_path, size_bytes=archive_path.stat().st_size,
        uploaded_to_s3=uploaded, s3_error=s3_error,
    )
