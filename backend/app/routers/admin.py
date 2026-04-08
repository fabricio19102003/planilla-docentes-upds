from __future__ import annotations

import logging
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/admin", tags=["admin"])

BACKUP_DIR = Path(__file__).resolve().parents[2] / "data" / "backups"
BACKUP_DIR.mkdir(parents=True, exist_ok=True)


@router.post("/backup")
def create_backup(
    request: Request,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Create a PostgreSQL database backup using pg_dump."""
    try:
        db_url = os.environ.get("DATABASE_URL", "")
        if not db_url:
            raise HTTPException(500, detail="DATABASE_URL not configured")

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"sipad_backup_{timestamp}.sql"
        filepath = BACKUP_DIR / filename

        # Parse DB URL to get connection params
        # Format: postgresql://user:pass@host:port/dbname
        parsed = urlparse(db_url)

        env = os.environ.copy()
        env["PGPASSWORD"] = parsed.password or ""

        cmd = [
            "pg_dump",
            "-h", parsed.hostname or "localhost",
            "-p", str(parsed.port or 5432),
            "-U", parsed.username or "postgres",
            "-d", parsed.path.lstrip("/"),
            "-f", str(filepath),
            "--no-owner",
            "--no-acl",
        ]

        result = subprocess.run(cmd, env=env, capture_output=True, text=True, timeout=120)

        if result.returncode != 0:
            raise HTTPException(500, detail=f"pg_dump failed: {result.stderr[:200]}")

        file_size = filepath.stat().st_size

        log_activity(
            db,
            "create_backup",
            "admin",
            f"Backup creado: {filename} ({file_size} bytes)",
            user=current_user,
            details={"filename": filename, "size": file_size},
            request=request,
        )
        db.commit()

        return {
            "success": True,
            "filename": filename,
            "file_size": file_size,
            "created_at": datetime.now().isoformat(),
        }
    except HTTPException:
        raise
    except subprocess.TimeoutExpired:
        raise HTTPException(500, detail="Backup timed out (>120s)")
    except FileNotFoundError:
        raise HTTPException(500, detail="pg_dump not found. Ensure PostgreSQL client tools are installed.")
    except Exception as exc:
        logger.exception("Backup creation failed: %s", exc)
        raise HTTPException(500, detail=f"Backup failed: {str(exc)[:200]}")


@router.get("/backups")
def list_backups(
    _: User = Depends(require_admin),
):
    """List available database backups."""
    backups = []
    for f in sorted(BACKUP_DIR.glob("sipad_backup_*.sql"), reverse=True):
        backups.append({
            "filename": f.name,
            "file_size": f.stat().st_size,
            "created_at": datetime.fromtimestamp(f.stat().st_mtime).isoformat(),
        })
    return backups


@router.get("/backups/{filename}/download")
def download_backup(
    filename: str,
    _: User = Depends(require_admin),
):
    """Download a backup file."""
    filepath = BACKUP_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("sipad_backup_"):
        raise HTTPException(404, detail="Backup no encontrado")

    return FileResponse(
        path=filepath,
        filename=filename,
        media_type="application/sql",
    )


@router.delete("/backups/{filename}")
def delete_backup(
    request: Request,
    filename: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Delete a backup file."""
    filepath = BACKUP_DIR / filename
    if not filepath.exists() or not filepath.name.startswith("sipad_backup_"):
        raise HTTPException(404, detail="Backup no encontrado")

    filepath.unlink()

    log_activity(
        db,
        "delete_backup",
        "admin",
        f"Backup eliminado: {filename}",
        user=current_user,
        request=request,
    )
    db.commit()

    return {"success": True}
