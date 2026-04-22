from __future__ import annotations

import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import FileResponse
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.planilla import PlanillaOutput
from app.models.report import Report
from app.models.user import User
from app.services import app_settings_service
from app.services.report_generator import ReportGenerator
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
                group_code=group_code,
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
            # Respect the discount_mode stored on the approved planilla (if any).
            # Otherwise the preview would always recalculate in "attendance" mode and
            # differ from the actual published totals when the planilla was generated
            # in "full" mode.
            stored_fin = (
                db.query(PlanillaOutput)
                .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
                .order_by(PlanillaOutput.generated_at.desc())
                .first()
            )
            fin_dm = stored_fin.discount_mode if stored_fin else "attendance"
            planilla_rows, detail_rows, gen_warnings = gen._build_planilla_data(
                db, month=month, year=year, discount_mode=fin_dm,
            )
            rows = planilla_rows
            if teacher_ci:
                rows = [r for r in rows if r.teacher_ci == teacher_ci]
            if semester:
                rows = [r for r in rows if r.semester and r.semester.upper() == semester.upper()]
            if group_code:
                rows = [r for r in rows if r.group_code == group_code]
            if subject:
                rows = [r for r in rows if subject.lower() in r.subject.lower()]

            # Prefer stored PlanillaOutput total (reflects admin overrides) when no row filter
            if not teacher_ci and not semester and not group_code and not subject:
                stored = (
                    db.query(PlanillaOutput)
                    .filter(PlanillaOutput.month == month, PlanillaOutput.year == year)
                    .order_by(PlanillaOutput.generated_at.desc())
                    .first()
                )
                total_payment = float(stored.total_payment) if stored else sum(r.final_payment for r in rows)
            else:
                total_payment = sum(r.final_payment for r in rows)

            return {
                "report_type": "financial",
                "total_teachers": len(set(r.teacher_ci for r in rows)),
                "total_designations": len(rows),
                "total_base_hours": sum(r.base_monthly_hours for r in rows),
                "total_absent_hours": sum(r.absent_hours for r in rows),
                "total_payable_hours": sum(r.payable_hours for r in rows),
                "total_gross_payment": sum(r.calculated_payment for r in rows),
                "total_retention": sum(r.retention_amount for r in rows),
                "total_payment": total_payment,  # net — after retention (stored when available)
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
                        "calculated_payment": r.calculated_payment,  # gross
                        "retention_amount": r.retention_amount,
                        "final_payment": r.final_payment,            # net
                    }
                    for r in sorted(rows, key=lambda x: (-x.final_payment, x.teacher_name))
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
                # Look up the stored planilla for this month first so we can reuse
                # its discount_mode when computing rows — without this, months
                # generated in "full" mode would be recomputed in "attendance" mode
                # here and show inconsistent totals.
                stored_m = (
                    db.query(PlanillaOutput)
                    .filter(PlanillaOutput.month == m, PlanillaOutput.year == year)
                    .order_by(PlanillaOutput.generated_at.desc())
                    .first()
                )
                m_dm = stored_m.discount_mode if stored_m else "attendance"
                planilla_rows, detail_rows, warn_rows = gen._build_planilla_data(
                    db, month=m, year=year, discount_mode=m_dm,
                )
                rows = planilla_rows
                if teacher_ci:
                    rows = [r for r in rows if r.teacher_ci == teacher_ci]

                # Prefer stored PlanillaOutput total when no teacher filter
                if not teacher_ci:
                    month_total = float(stored_m.total_payment) if stored_m else sum(r.final_payment for r in rows)
                else:
                    month_total = sum(r.final_payment for r in rows)  # net — after retention

                monthly_data.append({
                    'month': m,
                    'month_name': MN.get(m, str(m)),
                    'teachers': len(set(r.teacher_ci for r in rows)),
                    'base_hours': sum(r.base_monthly_hours for r in rows),
                    'absent_hours': sum(r.absent_hours for r in rows),
                    'payable_hours': sum(r.payable_hours for r in rows),
                    'total_payment': month_total,
                })

            return {
                "report_type": "comparative",
                "year": year,
                "months": monthly_data,
                "grand_total": sum(m['total_payment'] for m in monthly_data),
            }

        elif report_type == 'roster':
            from app.models.teacher import Teacher
            from app.models.designation import Designation
            from collections import Counter

            teachers = db.query(Teacher).filter(~Teacher.ci.startswith("TEMP-")).order_by(Teacher.full_name).all()
            desig_counts: Counter[str] = Counter()
            all_desigs = db.query(Designation).filter(
                Designation.academic_period == app_settings_service.get_active_academic_period(db)
            ).all()
            for d in all_desigs:
                desig_counts[d.teacher_ci] += 1

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

            all_teacher_cis = {
                r[0] for r in db.query(Designation.teacher_ci)
                .filter(Designation.academic_period == app_settings_service.get_active_academic_period(db))
                .distinct().all()
            }

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
            from app.models.biometric import BiometricRecord, BiometricUpload
            from app.models.teacher import Teacher
            from collections import defaultdict

            if not month or not year:
                raise HTTPException(400, detail="month and year required for reconciliation reports")

            att_records = db.query(AttendanceRecord).filter(
                AttendanceRecord.month == month, AttendanceRecord.year == year,
            ).all()

            designations = db.query(Designation).filter(
                Designation.academic_period == app_settings_service.get_active_academic_period(db)
            ).all()

            teacher_cis = set(d.teacher_ci for d in designations)
            teacher_names = {t.ci: t.full_name for t in db.query(Teacher).filter(Teacher.ci.in_(teacher_cis)).all()}

            att_by_teacher: dict = defaultdict(list)
            for r in att_records:
                att_by_teacher[r.teacher_ci].append(r)

            desig_by_teacher: dict = defaultdict(list)
            for d in designations:
                desig_by_teacher[d.teacher_ci].append(d)

            discrepancies = []
            for ci in sorted(teacher_cis):
                if ci.startswith("TEMP-"):
                    continue
                name = teacher_names.get(ci, ci)
                teacher_att = att_by_teacher.get(ci, [])
                teacher_desigs = desig_by_teacher.get(ci, [])

                expected_monthly_hours = sum(d.monthly_hours or 0 for d in teacher_desigs)

                if not teacher_att:
                    discrepancies.append({
                        "teacher_ci": ci,
                        "teacher_name": name,
                        "type": "no_records",
                        "description": "Sin registros de asistencia",
                        "expected_hours": expected_monthly_hours,
                        "actual_hours": 0,
                        "severity": "high",
                    })
                    continue

                absences = sum(1 for r in teacher_att if r.status == "ABSENT")
                total = len(teacher_att)
                absence_rate = absences / total if total > 0 else 0
                attended_hours = sum(r.academic_hours for r in teacher_att if r.status in ("ATTENDED", "LATE"))

                already_added = False
                if absence_rate > 0.3:
                    discrepancies.append({
                        "teacher_ci": ci,
                        "teacher_name": name,
                        "type": "high_absence",
                        "description": f"Tasa de ausencia: {absence_rate*100:.0f}% ({absences}/{total} clases)",
                        "expected_hours": expected_monthly_hours,
                        "actual_hours": attended_hours,
                        "severity": "high" if absence_rate > 0.5 else "medium",
                    })
                    already_added = True

                if expected_monthly_hours > 0 and attended_hours < expected_monthly_hours * 0.5:
                    if not already_added:
                        discrepancies.append({
                            "teacher_ci": ci,
                            "teacher_name": name,
                            "type": "hours_mismatch",
                            "description": f"Horas asistidas ({attended_hours}h) < 50% de esperadas ({expected_monthly_hours}h)",
                            "expected_hours": expected_monthly_hours,
                            "actual_hours": attended_hours,
                            "severity": "medium",
                        })

            return {
                "report_type": "reconciliation",
                "month": month,
                "year": year,
                "total_teachers": len(teacher_cis),
                "total_discrepancies": len(discrepancies),
                "high_severity": sum(1 for d in discrepancies if d["severity"] == "high"),
                "medium_severity": sum(1 for d in discrepancies if d["severity"] == "medium"),
                "discrepancies": discrepancies,
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
