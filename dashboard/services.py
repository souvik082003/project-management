"""
Business logic service layer for dashboard and notification management.
Aggregates role-specific metrics reusing existing core services.
"""

from datetime import timedelta

from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.http import Http404
from django.utils import timezone

from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from projects import services as project_services
from reviews import services as reviews_services
from submissions.models import Submission

from .models import Notification


def get_student_dashboard_data(student) -> dict:
    """
    UC17 Student Dashboard Aggregator:
    Reuses UC05 (assignments), UC13 (feedback), UC15 (marks).
    Provides status distributions, 7-day upcoming deadlines, active task queue.
    """
    if not getattr(student, "is_student", False):
        raise PermissionDenied("Only students can access student dashboard metrics.")

    assignments = assignment_services.get_student_assignments(student)
    now = timezone.now()
    seven_days_later = now + timedelta(days=7)

    # 1. Projects by status breakdown
    status_counts = {choice[0]: 0 for choice in AssignmentStatus.choices}
    status_counts.update(
        {
            "assigned": 0,
            "in_progress": 0,
            "overdue": 0,
            "submitted": 0,
            "under_review": 0,
            "revision_requested": 0,
            "evaluated": 0,
        }
    )
    for assign in assignments:
        if assign.status in status_counts:
            status_counts[assign.status] += 1
            safe_key = assign.status.lower().replace(" ", "_")
            status_counts[safe_key] = status_counts.get(safe_key, 0) + 1

    # 2. Deadlines in next 7 days
    upcoming_deadlines = (
        assignments.filter(project__deadline__gte=now, project__deadline__lte=seven_days_later)
        .exclude(status__in=[AssignmentStatus.EVALUATED])
        .order_by("project__deadline")
    )

    # 3. "Continue working" list (actionable assignments)
    continue_working = assignments.filter(
        status__in=[
            AssignmentStatus.IN_PROGRESS,
            AssignmentStatus.REVISION_REQUESTED,
            AssignmentStatus.ASSIGNED,
            AssignmentStatus.OVERDUE,
        ]
    ).order_by("project__deadline")

    # 4. Latest feedback (top 5)
    latest_feedbacks = reviews_services.get_student_feedbacks(student)[:5]

    # 5. Latest published marks (top 5)
    latest_marks = reviews_services.get_student_marks(student)[:5]

    return {
        "total_assignments": assignments.count(),
        "status_counts": status_counts,
        "upcoming_deadlines": upcoming_deadlines,
        "continue_working": continue_working,
        "latest_feedbacks": latest_feedbacks,
        "latest_marks": latest_marks,
    }


def get_teacher_dashboard_data(teacher) -> dict:
    """
    UC17 Teacher Dashboard Aggregator:
    Reuses UC03 (projects), UC08 (progress monitoring), and submissions.
    Provides project counts, status distributions, pending reviews, overdue student alerts,
    and Chart.js data.
    """
    if not getattr(teacher, "is_teacher", False):
        raise PermissionDenied("Only teachers can access teacher dashboard metrics.")

    projects = project_services.get_teacher_projects(teacher).annotate(
        num_assignments=Count("assignments", distinct=True)
    )

    # All assignments across teacher's projects
    assignments = ProjectAssignment.objects.filter(project__created_by=teacher).select_related("project", "student")

    status_counts = {choice[0]: 0 for choice in AssignmentStatus.choices}
    status_counts.update(
        {
            "assigned": 0,
            "in_progress": 0,
            "overdue": 0,
            "submitted": 0,
            "under_review": 0,
            "revision_requested": 0,
            "evaluated": 0,
        }
    )
    for assign in assignments:
        if assign.status in status_counts:
            status_counts[assign.status] += 1
            safe_key = assign.status.lower().replace(" ", "_")
            status_counts[safe_key] = status_counts.get(safe_key, 0) + 1

    # Submissions waiting for teacher review
    submissions_waiting = (
        Submission.objects.filter(
            assignment__project__created_by=teacher, assignment__status__in=[AssignmentStatus.SUBMITTED]
        )
        .select_related("assignment", "assignment__project", "assignment__student")
        .order_by("-submitted_on")
    )

    # Overdue student assignments
    overdue_assignments = assignments.filter(status=AssignmentStatus.OVERDUE).order_by("project__deadline")

    # Chart.js dataset
    chart_labels = [
        AssignmentStatus.ASSIGNED.label,
        AssignmentStatus.IN_PROGRESS.label,
        AssignmentStatus.SUBMITTED.label,
        AssignmentStatus.UNDER_REVIEW.label,
        AssignmentStatus.REVISION_REQUESTED.label,
        AssignmentStatus.OVERDUE.label,
        AssignmentStatus.EVALUATED.label,
    ]
    chart_data = [
        status_counts[AssignmentStatus.ASSIGNED],
        status_counts[AssignmentStatus.IN_PROGRESS],
        status_counts[AssignmentStatus.SUBMITTED],
        status_counts[AssignmentStatus.UNDER_REVIEW],
        status_counts[AssignmentStatus.REVISION_REQUESTED],
        status_counts[AssignmentStatus.OVERDUE],
        status_counts[AssignmentStatus.EVALUATED],
    ]

    return {
        "projects": projects,
        "total_projects": projects.count(),
        "total_students_assigned": assignments.count(),
        "status_counts": status_counts,
        "submissions_waiting": submissions_waiting,
        "overdue_assignments": overdue_assignments,
        "chart_labels": chart_labels,
        "chart_data": chart_data,
    }


def get_user_notifications(user):
    """Returns all notifications for the given user, newest first."""
    return user.notifications.all().order_by("-created_at")


def mark_notification_as_read(user, notification_id: int) -> Notification:
    """Marks a single user notification as read."""
    try:
        notification = user.notifications.get(pk=notification_id)
        notification.is_read = True
        notification.save(update_fields=["is_read"])
        return notification
    except Notification.DoesNotExist:
        raise Http404("Notification not found.")


def mark_all_notifications_as_read(user) -> int:
    """Marks all unread notifications of the user as read."""
    return user.notifications.filter(is_read=False).update(is_read=True)
