"""
Business logic service layer for assignments module.
Manages student project allocations, state transitions, notifications, and overdue tracking.
"""

import logging

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone

from projects import services as project_services
from projects.models import Project, ProjectStatus

from .models import AssignmentStatus, ProjectAssignment

logger = logging.getLogger("pms")
User = get_user_model()


class InvalidTransition(Exception):
    """Raised when an illegal assignment status transition is attempted."""


VALID_ASSIGNMENT_TRANSITIONS = {
    AssignmentStatus.ASSIGNED: {AssignmentStatus.IN_PROGRESS},
    AssignmentStatus.IN_PROGRESS: {AssignmentStatus.IN_PROGRESS, AssignmentStatus.OVERDUE, AssignmentStatus.SUBMITTED},
    AssignmentStatus.OVERDUE: {AssignmentStatus.SUBMITTED},
    AssignmentStatus.SUBMITTED: {AssignmentStatus.UNDER_REVIEW},
    AssignmentStatus.UNDER_REVIEW: {AssignmentStatus.REVISION_REQUESTED, AssignmentStatus.EVALUATED},
    AssignmentStatus.REVISION_REQUESTED: {AssignmentStatus.IN_PROGRESS},
}


def transition(assignment: ProjectAssignment, target_status: str) -> ProjectAssignment:
    """
    Validates and executes a state transition on a ProjectAssignment.
    Raises InvalidTransition on illegal transitions.
    Never set assignment.status directly anywhere else.
    """
    allowed_next_states = VALID_ASSIGNMENT_TRANSITIONS.get(assignment.status, set())
    if target_status not in allowed_next_states:
        raise InvalidTransition(f"Cannot transition ProjectAssignment from '{assignment.status}' to '{target_status}'.")

    old_status = assignment.status
    assignment.status = target_status
    assignment.save(update_fields=["status"])
    logger.info(
        f"ProjectAssignment '{assignment.id}' (Student={assignment.student.email}) transitioned: "
        f"{old_status} -> {target_status}"
    )
    return assignment


def notify_assignment(assignment: ProjectAssignment) -> None:
    """
    Notifies student of project allocation via email and in-app alert.
    Never lets notification failure break assignment creation.
    """
    try:
        from dashboard import notifications as dashboard_notifications

        dashboard_notifications.notify_assignment(assignment)
    except Exception as err:
        logger.warning(f"Assignment notification failed (non-blocking): {err}")


def assign_students_to_project(teacher, project: Project, student_ids: list[int]) -> tuple[int, int]:
    """
    Assigns one or more students to a project.
    Skips students already assigned.
    Transitions Project Draft -> Assigned on first assignment.
    Calls notify_assignment() stub for newly assigned students.
    Returns (assigned_count, skipped_count).
    """
    if project.created_by_id != teacher.id:
        raise Http404("Project not found.")

    if not student_ids:
        raise ValidationError("Please select at least one student to assign.")

    students = User.objects.filter(id__in=student_ids, role="student")
    assigned_count = 0
    skipped_count = 0

    for student in students:
        # Check if already assigned
        if ProjectAssignment.objects.filter(project=project, student=student).exists():
            skipped_count += 1
            continue

        assignment = ProjectAssignment.objects.create(
            project=project, student=student, status=AssignmentStatus.ASSIGNED
        )
        assigned_count += 1
        notify_assignment(assignment)

    # Flip Draft -> Assigned if at least one student was assigned
    if assigned_count > 0 and project.status == ProjectStatus.DRAFT:
        project_services.transition(project, ProjectStatus.ASSIGNED)

    logger.info(
        f"Assigned students to Project '{project.id}': {assigned_count} newly assigned, {skipped_count} skipped."
    )
    return assigned_count, skipped_count


def get_student_assignments(student, status: str | None = None):
    """
    Returns queryset of assignments belonging to a student.
    Optionally filtered by assignment status.
    """
    qs = (
        ProjectAssignment.objects.filter(student=student)
        .select_related("project", "project__created_by")
        .order_by("-assigned_on")
    )

    if status and status in AssignmentStatus.values:
        qs = qs.filter(status=status)

    return qs


def get_student_assignment_or_404(assignment_id: int, student) -> ProjectAssignment:
    """
    Retrieves an assignment belonging to the student or raises Http404.
    A student cannot view another student's assignment.
    """
    try:
        return ProjectAssignment.objects.select_related("project", "project__created_by").get(
            pk=assignment_id, student=student
        )
    except ProjectAssignment.DoesNotExist:
        raise Http404("Assignment not found.")


def mark_overdue_assignments(now=None) -> int:
    """
    Transitions In progress -> Overdue for all assignments whose project deadline
    has passed and have not yet submitted.
    Returns the number of assignments marked overdue.
    """
    current_time = now or timezone.now()
    overdue_assignments = ProjectAssignment.objects.filter(
        status=AssignmentStatus.IN_PROGRESS, project__deadline__lt=current_time
    )

    count = 0
    for assignment in overdue_assignments:
        try:
            transition(assignment, AssignmentStatus.OVERDUE)
            count += 1
        except InvalidTransition as e:
            logger.warning(f"Failed to mark assignment {assignment.id} as overdue: {e}")

    logger.info(f"Marked {count} assignments as Overdue at {current_time}.")
    return count


def send_deadline_reminders(now=None) -> int:
    """
    Finds active assignments whose project deadline is approaching within 2 days
    (now < deadline <= now + 2 days), where a reminder has not already been sent.
    Sends notification email and in-app alert, setting deadline_reminder_sent=True.
    Emails only the right students, once.
    Returns the count of reminders dispatched.
    """
    from datetime import timedelta

    current_time = now or timezone.now()
    two_days_later = current_time + timedelta(days=2)

    active_statuses = [AssignmentStatus.ASSIGNED, AssignmentStatus.IN_PROGRESS, AssignmentStatus.REVISION_REQUESTED]

    assignments_to_remind = ProjectAssignment.objects.filter(
        deadline_reminder_sent=False,
        status__in=active_statuses,
        project__deadline__gt=current_time,
        project__deadline__lte=two_days_later,
    ).select_related("project", "student")

    count = 0
    from dashboard import notifications as dashboard_notifications

    for assign in assignments_to_remind:
        dashboard_notifications.notify_deadline_reminder(assign)
        assign.deadline_reminder_sent = True
        assign.save(update_fields=["deadline_reminder_sent"])
        count += 1
        logger.info(f"Deadline reminder sent to {assign.student.email} for Project '{assign.project.title}'")

    return count
