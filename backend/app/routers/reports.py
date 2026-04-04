from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import Report
from app.models.user import User
from app.services.report_generator import ReportGenerator
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
def generate_report(
    report_type: str = Query(..., description="financial, attendance, or comparative"),
    month: int = Query(None),
    year: int = Query(None),
    teacher_ci: str = Query(None),
    semester: str = Query(None),
    group_code: str = Query(None),
    subject: str = Query(None),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Generate a PDF report and save it."""
    try:
        gen = ReportGenerator()

        if report_type == 'financial':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for financial reports")
            report = gen.generate_financial_report(
                db, month=month, year=year,
                teacher_ci=teacher_ci, semester=semester,
                group_code=group_code, subject=subject,
                generated_by=current_user.id,
            )
        elif report_type == 'attendance':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for attendance reports")
            report = gen.generate_attendance_report(
                db, month=month, year=year,
                teacher_ci=teacher_ci, semester=semester,
                group_code=group_code,
                generated_by=current_user.id,
            )
        elif report_type == 'comparative':
            if not year:
                raise HTTPException(status_code=400, detail="year is required for comparative reports")
            report = gen.generate_comparative_report(
                db, year=year, teacher_ci=teacher_ci,
                generated_by=current_user.id,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

        db.commit()

        return {
            "id": report.id,
            "report_type": report.report_type,
            "title": report.title,
            "description": report.description,
            "file_size": report.file_size,
            "generated_at": report.generated_at.isoformat(),
            "status": report.status,
        }
    except HTTPException:
        raise
    except Exception as exc:
        db.rollback()
        logger.exception("Report generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo generar el reporte") from exc


@router.get("/history")
def report_history(
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """List all previously generated reports."""
    reports = db.query(Report).order_by(desc(Report.generated_at)).limit(50).all()
    return [
        {
            "id": r.id,
            "report_type": r.report_type,
            "title": r.title,
            "description": r.description,
            "file_size": r.file_size,
            "generated_at": r.generated_at.isoformat(),
            "status": r.status,
        }
        for r in reports
    ]


@router.get("/preview")
def preview_report(
    report_type: str = Query(...),
    month: int = Query(None),
    year: int = Query(None),
    teacher_ci: str = Query(None),
    semester: str = Query(None),
    group_code: str = Query(None),
    subject: str = Query(None),
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Return data that would go into the report (for preview without generating PDF)."""
    from app.models.attendance import AttendanceRecord
    from app.models.designation import Designation

    try:
        if report_type == 'financial':
            from app.services.planilla_generator import PlanillaGenerator
            gen = PlanillaGenerator()
            planilla_rows, detail_rows, gen_warnings = gen._build_planilla_data(db, month=month, year=year)
            rows = planilla_rows
            if teacher_ci:
                rows = [r for r in rows if r.teacher_ci == teacher_ci]
            if semester:
                rows = [r for r in rows if r.semester and r.semester.upper() == semester.upper()]
            if group_code:
                rows = [r for r in rows if r.group_code == group_code]
            if subject:
                rows = [r for r in rows if subject.lower() in r.subject.lower()]

            return {
                "report_type": "financial",
                "total_teachers": len(set(r.teacher_ci for r in rows)),
                "total_designations": len(rows),
                "total_base_hours": sum(r.base_monthly_hours for r in rows),
                "total_absent_hours": sum(r.absent_hours for r in rows),
                "total_payable_hours": sum(r.payable_hours for r in rows),
                "total_payment": sum(r.calculated_payment for r in rows),
                "rows": [
                    {
                        "teacher_ci": r.teacher_ci,
                        "teacher_name": r.teacher_name,
                        "subject": r.subject,
                        "group_code": r.group_code,
                        "semester": r.semester,
                        "base_monthly_hours": r.base_monthly_hours,
                        "absent_hours": r.absent_hours,
                        "payable_hours": r.payable_hours,
                        "calculated_payment": r.calculated_payment,
                    }
                    for r in sorted(rows, key=lambda x: (-x.calculated_payment, x.teacher_name))
                ],
            }

        elif report_type == 'attendance':
            query = db.query(AttendanceRecord).filter(
                AttendanceRecord.month == month,
                AttendanceRecord.year == year,
            )
            if teacher_ci:
                query = query.filter(AttendanceRecord.teacher_ci == teacher_ci)

            records = query.order_by(AttendanceRecord.date).all()

            # Filter by designation attributes if needed
            if semester or group_code:
                desig_ids = set(r.designation_id for r in records)
                desigs = {
                    d.id: d
                    for d in db.query(Designation).filter(Designation.id.in_(desig_ids)).all()
                } if desig_ids else {}
                filtered_ids: set[int] = set()
                for did, d in desigs.items():
                    if semester and d.semester.upper() != semester.upper():
                        continue
                    if group_code and d.group_code != group_code:
                        continue
                    filtered_ids.add(did)
                records = [r for r in records if r.designation_id in filtered_ids]

            attended = sum(1 for r in records if r.status == 'ATTENDED')
            late = sum(1 for r in records if r.status == 'LATE')
            absent = sum(1 for r in records if r.status == 'ABSENT')

            return {
                "report_type": "attendance",
                "total_records": len(records),
                "attended": attended,
                "late": late,
                "absent": absent,
                "attendance_rate": round((attended + late) / len(records) * 100, 1) if records else 0,
                "records_sample": [
                    {
                        "date": r.date.isoformat() if r.date else None,
                        "teacher_ci": r.teacher_ci,
                        "status": r.status,
                        "check_in": r.actual_entry.strftime('%H:%M') if r.actual_entry else None,
                        "check_out": r.actual_exit.strftime('%H:%M') if r.actual_exit else None,
                        "academic_hours": r.academic_hours,
                    }
                    for r in records[:50]
                ],
            }

        elif report_type == 'comparative':
            from app.services.planilla_generator import PlanillaGenerator as PG
            from app.services.report_generator import MONTH_NAMES as MN

            months_query = db.query(
                AttendanceRecord.month
            ).filter(AttendanceRecord.year == year).distinct().order_by(AttendanceRecord.month).all()
            months = [m[0] for m in months_query]

            gen = PG()
            monthly_data = []
            for m in months:
                planilla_rows, detail_rows, warn_rows = gen._build_planilla_data(db, month=m, year=year)
                rows = planilla_rows
                if teacher_ci:
                    rows = [r for r in rows if r.teacher_ci == teacher_ci]
                monthly_data.append({
                    'month': m,
                    'month_name': MN.get(m, str(m)),
                    'teachers': len(set(r.teacher_ci for r in rows)),
                    'base_hours': sum(r.base_monthly_hours for r in rows),
                    'absent_hours': sum(r.absent_hours for r in rows),
                    'payable_hours': sum(r.payable_hours for r in rows),
                    'total_payment': sum(r.calculated_payment for r in rows),
                })

            return {
                "report_type": "comparative",
                "year": year,
                "months": monthly_data,
                "grand_total": sum(m['total_payment'] for m in monthly_data),
            }

        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Report preview failed: %s", exc)
        raise HTTPException(status_code=500, detail="No se pudo generar la previsualización") from exc


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    _: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Download a previously generated report PDF."""
    report = db.query(Report).filter(Report.id == report_id).first()
    if report is None:
        raise HTTPException(status_code=404, detail="Reporte no encontrado")

    file_path = Path(report.file_path or "")
    if not report.file_path or not file_path.exists():
        raise HTTPException(status_code=404, detail="Archivo de reporte no encontrado")

    return FileResponse(
        path=file_path,
        filename=file_path.name,
        media_type="application/pdf",
    )
