from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.report import Report
from app.models.user import User
from app.services import app_settings_service
from app.services.report_generator import ReportGenerator
from app.services.planilla_generator import PayrollDataError
from app.services.monetary_snapshot import SnapshotReconciliationError
from app.services.activity_logger import log_activity
from app.utils.auth import require_admin

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/reports", tags=["reports"])


@router.post("/generate")
def generate_report(
    request: Request,
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
        user_name = current_user.full_name

        if report_type == 'financial':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for financial reports")
            report = gen.generate_financial_report(
                db, month=month, year=year,
                teacher_ci=teacher_ci, semester=semester,
                group_code=group_code, subject=subject,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        elif report_type == 'attendance':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for attendance reports")
            report = gen.generate_attendance_report(
                db, month=month, year=year,
                teacher_ci=teacher_ci, semester=semester,
                group_code=group_code, subject=subject,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        elif report_type == 'comparative':
            if not year:
                raise HTTPException(status_code=400, detail="year is required for comparative reports")
            report = gen.generate_comparative_report(
                db, year=year, teacher_ci=teacher_ci,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        elif report_type == 'roster':
            report = gen.generate_roster_report(
                db,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        elif report_type == 'incidence':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for incidence reports")
            report = gen.generate_incidence_report(
                db, month=month, year=year,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        elif report_type == 'reconciliation':
            if not month or not year:
                raise HTTPException(status_code=400, detail="month and year are required for reconciliation reports")
            report = gen.generate_reconciliation_report(
                db, month=month, year=year,
                generated_by=current_user.id,
                generated_by_name=user_name,
            )
        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

        log_activity(
            db,
            "generate_report",
            "reports",
            f"Reporte generado: {report.title}",
            user=current_user,
            details={"report_type": report_type, "report_id": report.id},
            request=request,
        )

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
    except (PayrollDataError, SnapshotReconciliationError) as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail=exc.as_detail()) from exc
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
    try:
        if report_type == 'financial':
            return ReportGenerator().build_financial_dataset(
                db, month=month, year=year, teacher_ci=teacher_ci,
                semester=semester, group_code=group_code, subject=subject,
            )

        elif report_type == 'attendance':
            return ReportGenerator().build_attendance_dataset(
                db,
                month=month,
                year=year,
                teacher_ci=teacher_ci,
                semester=semester,
                group_code=group_code,
                subject=subject,
            ).as_preview()

        elif report_type == 'comparative':
            return ReportGenerator().build_comparative_dataset(
                db,
                year=year,
                teacher_ci=teacher_ci,
            )

        elif report_type == 'roster':
            from app.models.teacher import Teacher
            from collections import Counter

            teachers = db.query(Teacher).filter(~Teacher.ci.startswith("TEMP-")).order_by(Teacher.full_name).all()
            desig_counts: Counter[str] = Counter()
            from app.services.teacher_workload_service import active_period_effective_date, effective_workloads
            academic_period = app_settings_service.get_active_academic_period(db)
            workloads = effective_workloads(
                db,
                academic_period=academic_period,
                target_date=active_period_effective_date(academic_period),
            )
            for workload in workloads:
                desig_counts[workload.teacher_ci] += 1

            with_retention = sum(1 for t in teachers if (t.invoice_retention or "").upper() == "RETENCION")
            with_nit = sum(1 for t in teachers if t.nit)

            return {
                "report_type": "roster",
                "total_teachers": len(teachers),
                "with_nit": with_nit,
                "with_retention": with_retention,
                "rows": [
                    {
                        "ci": t.ci,
                        "full_name": t.full_name,
                        "phone": t.phone,
                        "email": t.email,
                        "bank": t.bank,
                        "account_number": t.account_number,
                        "nit": t.nit,
                        "invoice_retention": t.invoice_retention,
                        "designation_count": desig_counts.get(t.ci, 0),
                    }
                    for t in teachers[:50]
                ],
            }

        elif report_type == 'incidence':
            from app.models.biometric import BiometricRecord, BiometricUpload
            from app.models.teacher import Teacher
            from collections import defaultdict

            if not month or not year:
                raise HTTPException(400, detail="month and year required for incidence reports")

            records = db.query(AttendanceRecord).filter(
                AttendanceRecord.month == month,
                AttendanceRecord.year == year,
            ).all()

            bio_cis = {
                r[0] for r in db.query(BiometricRecord.teacher_ci)
                .join(BiometricUpload)
                .filter(BiometricUpload.month == month, BiometricUpload.year == year)
                .distinct().all()
            }

            all_teacher_cis = {record.teacher_ci for record in records}

            teachers_without_bio = all_teacher_cis - bio_cis
            teacher_names = {
                t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(all_teacher_cis)).all()
            }

            teacher_stats: dict = defaultdict(lambda: {"absences": 0, "lates": 0, "late_minutes_total": 0, "total_slots": 0, "attended": 0})
            for r in records:
                ts = teacher_stats[r.teacher_ci]
                ts["total_slots"] += 1
                if r.status == "ABSENT":
                    ts["absences"] += 1
                elif r.status == "LATE":
                    ts["lates"] += 1
                    ts["late_minutes_total"] += r.late_minutes
                elif r.status == "ATTENDED":
                    ts["attended"] += 1

            top_absentees = sorted(
                [{"teacher_ci": ci, "teacher_name": teacher_names.get(ci, ci), **stats}
                 for ci, stats in teacher_stats.items() if stats["absences"] > 0],
                key=lambda x: -x["absences"]
            )[:20]

            top_lates = sorted(
                [{"teacher_ci": ci, "teacher_name": teacher_names.get(ci, ci), **stats}
                 for ci, stats in teacher_stats.items() if stats["lates"] > 0],
                key=lambda x: -x["lates"]
            )[:20]

            without_bio_list = [
                {"teacher_ci": ci, "teacher_name": teacher_names.get(ci, ci)}
                for ci in sorted(teachers_without_bio)
                if ci in teacher_names
            ]

            total_absences = sum(1 for r in records if r.status == "ABSENT")
            total_lates = sum(1 for r in records if r.status == "LATE")

            return {
                "report_type": "incidence",
                "month": month,
                "year": year,
                "total_records": len(records),
                "total_absences": total_absences,
                "total_lates": total_lates,
                "teachers_without_biometric": len(without_bio_list),
                "top_absentees": top_absentees,
                "top_lates": top_lates,
                "without_biometric": without_bio_list,
            }

        elif report_type == 'reconciliation':
            if not month or not year:
                raise HTTPException(400, detail="month and year required for reconciliation reports")
            return ReportGenerator().build_reconciliation_dataset(
                db,
                month=month,
                year=year,
            ).as_preview()

        else:
            raise HTTPException(status_code=400, detail=f"Unknown report type: {report_type}")

    except HTTPException:
        raise
    except (PayrollDataError, SnapshotReconciliationError) as exc:
        raise HTTPException(status_code=409, detail=exc.as_detail()) from exc
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
