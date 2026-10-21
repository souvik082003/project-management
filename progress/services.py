"""
Business logic service layer for progress module.
Manages student progress submissions, validations, teacher monitoring, and reports.
"""

import csv
import io
import logging
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone

from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from projects.models import Project

from .models import ProgressUpdate

logger = logging.getLogger("pms")

ALLOWED_PROGRESS_STATUSES = {
    AssignmentStatus.ASSIGNED,
    AssignmentStatus.IN_PROGRESS,
    AssignmentStatus.OVERDUE,
    AssignmentStatus.REVISION_REQUESTED,
}

DISALLOWED_PROGRESS_STATUSES = {
    AssignmentStatus.SUBMITTED,
    AssignmentStatus.UNDER_REVIEW,
    AssignmentStatus.EVALUATED,
}


def add_progress_update(
    student, assignment: ProjectAssignment, percent_complete: int, remarks: str = ""
) -> ProgressUpdate:
    """
    Submits a milestone progress update for an assignment.
    Rules:
      - Student must own the assignment.
      - Disallowed once Submitted, Under review, or Evaluated.
      - percent_complete must be between 0 and 100.
      - percent_complete cannot be lower than the previous value.
      - First update moves Assigned -> In progress.
      - First update after Revision requested moves it back to In progress.
    """
    if assignment.student_id != student.id:
        raise Http404("Assignment not found.")

    if assignment.status in DISALLOWED_PROGRESS_STATUSES:
        raise ValidationError(
            f"Progress updates are not permitted while assignment status is '{assignment.get_status_display()}'."
        )

    try:
        percent = int(percent_complete)
    except (TypeError, ValueError):
        raise ValidationError({"percent_complete": "Completion percentage must be a valid number."})

    if percent < 0 or percent > 100:
        raise ValidationError({"percent_complete": "Completion percentage must be between 0 and 100."})

    latest_update = assignment.progress_updates.order_by("-updated_on").first()
    if latest_update and percent < latest_update.percent_complete:
        raise ValidationError(
            {
                "percent_complete": f"Completion percentage cannot decrease from previous value ({latest_update.percent_complete}%)."
            }
        )

    update = ProgressUpdate.objects.create(
        assignment=assignment, percent_complete=percent, remarks=(remarks or "").strip()
    )

    # State transitions:
    # 1. Assigned -> In progress on first update
    if assignment.status == AssignmentStatus.ASSIGNED or assignment.status == AssignmentStatus.REVISION_REQUESTED:
        assignment_services.transition(assignment, AssignmentStatus.IN_PROGRESS)

    logger.info(f"Progress update recorded: Assignment {assignment.id}, Student={student.email}, Percent={percent}%")
    return update


def get_progress_summary(teacher, project_id: int | None = None, status: str | None = None) -> list[dict]:
    """
    Retrieves progress overview of assignments for the teacher's projects.
    Enforces that teacher sees only their own projects.
    Computes overdue and stale update flags (amber if no update in 7 days).
    """
    qs = (
        ProjectAssignment.objects.filter(project__created_by=teacher)
        .select_related("project", "student")
        .order_by("-assigned_on")
    )

    if project_id:
        qs = qs.filter(project_id=project_id)

    if status and status in AssignmentStatus.values:
        qs = qs.filter(status=status)

    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    items = []

    for assignment in qs:
        latest = assignment.progress_updates.order_by("-updated_on").first()
        latest_percent = latest.percent_complete if latest else 0
        last_updated_on = latest.updated_on if latest else None

        # Overdue flag: assignment marked Overdue or deadline passed and not completed
        is_overdue = (assignment.status == AssignmentStatus.OVERDUE) or (
            assignment.is_past_deadline and assignment.status != AssignmentStatus.EVALUATED
        )

        # Stale flag (amber): no update in last 7 days
        if last_updated_on:
            is_stale = last_updated_on <= seven_days_ago
        else:
            is_stale = assignment.assigned_on <= seven_days_ago

        items.append(
            {
                "assignment": assignment,
                "student": assignment.student,
                "project": assignment.project,
                "latest_percent": latest_percent,
                "last_updated_on": last_updated_on,
                "days_remaining": assignment.days_remaining,
                "is_overdue": is_overdue,
                "is_stale": is_stale,
            }
        )

    return items


def get_project_progress_report(teacher, project_id: int) -> dict:
    """
    Generates structured progress report for a specific project.
    Calculates average completion and overdue counts.
    """
    try:
        project = Project.objects.get(pk=project_id, created_by=teacher)
    except Project.DoesNotExist:
        raise Http404("Project not found.")

    summary_items = get_progress_summary(teacher, project_id=project.id)
    total_students = len(summary_items)
    total_percent = sum(item["latest_percent"] for item in summary_items)
    overdue_count = sum(1 for item in summary_items if item["is_overdue"])

    avg_completion = round(total_percent / total_students, 1) if total_students > 0 else 0.0

    return {
        "project": project,
        "summary_items": summary_items,
        "total_students": total_students,
        "avg_completion": avg_completion,
        "overdue_count": overdue_count,
    }


def generate_progress_csv_report(teacher, project_id: int) -> str:
    """
    Generates CSV content for project progress report.
    """
    report = get_project_progress_report(teacher, project_id)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow(
        [
            "Student Name",
            "Roll Number",
            "Email",
            "Assignment Status",
            "Latest Progress (%)",
            "Last Update Date",
            "Days Remaining",
            "Overdue Alert",
            "Stale Alert (7d)",
        ]
    )

    for item in report["summary_items"]:
        writer.writerow(
            [
                item["student"].get_display_name(),
                item["student"].roll_no or "-",
                item["student"].email,
                item["assignment"].get_status_display(),
                f"{item['latest_percent']}%",
                item["last_updated_on"].strftime("%Y-%m-%d %H:%M") if item["last_updated_on"] else "No updates",
                item["days_remaining"],
                "YES" if item["is_overdue"] else "NO",
                "YES" if item["is_stale"] else "NO",
            ]
        )

    return output.getvalue()
