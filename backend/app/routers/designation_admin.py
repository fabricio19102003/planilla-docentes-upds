"""Admin endpoints for managing single designations (list, create, edit, finalize, delete)."""

from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.designation_admin import (
    DesignationClassroomRequest,
    DesignationAdminList,
    DesignationAdminMutation,
    DesignationFinalizeRequest,
    DesignationWriteRequest,
)
from app.services import designation_admin_service as service
from app.services import designation_room_import_service as room_import
from app.services.activity_logger import log_activity
from app.services.designation_bootstrap_preview import WorkbookValidationError, preflight_xlsx
from app.services.designation_schedule_loader_service import LoaderInputError
from app.utils.auth import require_admin

router = APIRouter(prefix="/api/admin/designations", tags=["designations"], dependencies=[Depends(require_admin)])


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, service.DesignationNotFound):
        return HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc))
    if isinstance(exc, service.DesignationInvalid):
        return HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={"message": "Revisá los datos de la designación.", "errors": exc.errors},
        )
    assert isinstance(exc, service.DesignationBlocked)
    return HTTPException(status.HTTP_409_CONFLICT, detail={
        "message": exc.message,
        "blockers": [item.model_dump(mode="json") for item in exc.blockers],
    })


_EXPECTED = (service.DesignationNotFound, service.DesignationInvalid, service.DesignationBlocked)


def _label(item) -> str:
    return f"{item.subject} {item.group_code} ({item.teacher_ci})"


MAX_WORKBOOK_BYTES = 20 * 1024 * 1024


async def _read_workbook(file: UploadFile) -> bytes:
    content = await file.read(MAX_WORKBOOK_BYTES + 1)
    if not content:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El Excel está vacío.")
    if len(content) > MAX_WORKBOOK_BYTES:
        raise HTTPException(status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="El Excel supera el límite de 20 MiB.")
    try:
        preflight_xlsx(content)
    except WorkbookValidationError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail="El archivo no es un Excel válido.") from exc
    return content


@router.post("/rooms/preview")
async def preview_rooms(file: UploadFile = File(), db: Session = Depends(get_db)):
    content = await _read_workbook(file)
    try:
        return room_import.preview(db, content)
    except LoaderInputError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc


@router.post("/rooms/apply")
async def apply_rooms(
    request: Request,
    file: UploadFile = File(),
    preview_digest: str = Form(min_length=64, max_length=64),
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    content = await _read_workbook(file)
    try:
        result = room_import.apply(db, content, preview_digest)
        log_activity(
            db, "apply_designation_rooms", "designations",
            f"Aulas de designaciones importadas ({result['academic_period']}): "
            f"{result['summary']['changed']} cambiadas",
            user=user,
            details={"academic_period": result["academic_period"], "summary": result["summary"],
                     "changed_designation_ids": result["changed_designation_ids"]},
            request=request,
        )
        db.commit()
        return result
    except LoaderInputError as exc:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc
    except room_import.StalePreview as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, detail="La vista previa cambió; volvé a generarla.") from exc
    except Exception:
        db.rollback()
        raise


@router.get("", response_model=DesignationAdminList)
def list_designations(
    academic_period: str | None = Query(default=None, max_length=20),
    teacher_ci: str | None = Query(default=None, max_length=20),
    q: str | None = Query(default=None, max_length=100),
    semester: str | None = Query(default=None, max_length=50),
    designation_type: Literal["regular", "practice"] | None = None,
    status_filter: Literal["active", "finalized", "all"] = Query(default="all", alias="status"),
    db: Session = Depends(get_db),
):
    return service.list_designations(
        db, academic_period=academic_period, teacher_ci=teacher_ci, q=q, semester=semester,
        designation_type=designation_type, status=status_filter,
    )


@router.post("", response_model=DesignationAdminMutation, status_code=status.HTTP_201_CREATED)
def create_designation(
    payload: DesignationWriteRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = service.create_designation(db, payload)
        log_activity(
            db, "create_designation", "designations", f"Designación creada: {_label(result)}",
            user=user, details={"designation_id": result.id, "designation": result.model_dump(mode="json",
                                include=set(service.TRACKED_FIELDS) | {"academic_period"})},
            request=request,
        )
        db.commit()
        return result
    except _EXPECTED as exc:
        # Every refusal happens before any write; a lost unique-key race rolls back in the service.
        raise _http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.put("/{designation_id}", response_model=DesignationAdminMutation)
def update_designation(
    designation_id: int,
    payload: DesignationWriteRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result, changes = service.update_designation(db, designation_id, payload)
        if changes:
            log_activity(
                db, "update_designation", "designations", f"Designación editada: {_label(result)}",
                user=user, details={"designation_id": result.id, "changes": changes}, request=request,
            )
            db.commit()
        return result
    except _EXPECTED as exc:
        # Every refusal happens before any write; a lost unique-key race rolls back in the service.
        raise _http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.put("/{designation_id}/classroom", response_model=DesignationAdminMutation)
def set_designation_classroom(
    designation_id: int,
    payload: DesignationClassroomRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result, changes = service.set_classroom(db, designation_id, payload.classroom_id)
        if changes:
            log_activity(
                db, "update_designation", "designations", f"Designación editada: {_label(result)}",
                user=user, details={"designation_id": result.id, "changes": changes}, request=request,
            )
            db.commit()
        return result
    except _EXPECTED as exc:
        raise _http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.post("/{designation_id}/finalize", response_model=DesignationAdminMutation)
def finalize_designation(
    designation_id: int,
    payload: DesignationFinalizeRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        result = service.finalize_designation(db, designation_id, payload.end_date)
        log_activity(
            db, "finalize_designation", "designations",
            f"Designación finalizada el {payload.end_date.isoformat()}: {_label(result)}",
            user=user, details={"designation_id": result.id, "end_date": payload.end_date.isoformat()},
            request=request,
        )
        db.commit()
        return result
    except _EXPECTED as exc:
        # Every refusal happens before any write; a lost unique-key race rolls back in the service.
        raise _http_error(exc) from exc
    except Exception:
        db.rollback()
        raise


@router.delete("/{designation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_designation(
    designation_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    try:
        deleted = service.delete_designation(db, designation_id)
        log_activity(
            db, "delete_designation", "designations",
            f"Designación eliminada: {deleted['subject']} {deleted['group_code']} ({deleted['teacher_ci']})",
            user=user, details={"designation_id": deleted["id"], "designation": deleted}, request=request,
        )
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except _EXPECTED as exc:
        # Every refusal happens before any write; a lost unique-key race rolls back in the service.
        raise _http_error(exc) from exc
    except Exception:
        db.rollback()
        raise
