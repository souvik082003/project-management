"""
Business logic service layer for projects module.
Enforces business rules for creating, editing, querying, and reporting projects.
"""
import csv
import io
import logging
from django.core.exceptions import ValidationError
from django.http import Http404
from django.utils import timezone
from django.db.models import Count
from .models import Project, ProjectStatus

logger = logging.getLogger('pms')


class InvalidTransition(Exception):
    """Raised when an illegal project status transition is attempted."""
    pass


VALID_PROJECT_TRANSITIONS = {
    ProjectStatus.DRAFT: {ProjectStatus.ASSIGNED},
    ProjectStatus.ASSIGNED: {ProjectStatus.CLOSED},
}


def transition(project: Project, target_status: str) -> Project:
    """
    Validates and executes a state transition on a Project.
    Only allows:
      Draft -> Assigned
      Assigned -> Closed
    Raises InvalidTransition on illegal transitions.
    """
    allowed_next_states = VALID_PROJECT_TRANSITIONS.get(project.status, set())
    if target_status not in allowed_next_states:
        raise InvalidTransition(
            f"Cannot transition Project from '{project.status}' to '{target_status}'."
        )

    old_status = project.status
    project.status = target_status
    project.save(update_fields=['status', 'updated_at'])
    logger.info(f"Project '{project.id}' transitioned: {old_status} -> {target_status}")
    return project


def create_project(teacher, title: str, description: str, deadline) -> Project:
    """
    Creates a new project in Draft status.
    Enforces teacher role and validates that deadline cannot be in the past.
    """
    if not getattr(teacher, 'is_teacher', False):
        raise ValidationError("Only teachers are permitted to create projects.")

    title = (title or "").strip()
    description = (description or "").strip()

    if not title:
        raise ValidationError({"title": "Project title is required."})

    if not description:
        raise ValidationError({"description": "Project description is required."})

    if not deadline:
        raise ValidationError({"deadline": "A valid deadline is required."})

    current_time = timezone.now()
    if deadline < current_time:
        raise ValidationError({"deadline": "Deadline cannot be in the past on creation."})

    project = Project.objects.create(
        title=title,
        description=description,
        deadline=deadline,
        created_by=teacher,
        status=ProjectStatus.DRAFT
    )
    logger.info(f"Project created: ID={project.id}, Title='{project.title}', Teacher={teacher.email}")
    return project


def update_project(project: Project, teacher, title: str, description: str, deadline) -> Project:
    """
    Updates an existing project.
    Enforces that only the creator teacher can update it.
    """
    if project.created_by_id != teacher.id:
        raise Http404("Project not found.")

    title = (title or "").strip()
    description = (description or "").strip()

    if not title:
        raise ValidationError({"title": "Project title is required."})

    if not description:
        raise ValidationError({"description": "Project description is required."})

    if not deadline:
        raise ValidationError({"deadline": "A valid deadline is required."})

    project.title = title
    project.description = description
    project.deadline = deadline
    project.save(update_fields=['title', 'description', 'deadline', 'updated_at'])
    logger.info(f"Project updated: ID={project.id} by Teacher={teacher.email}")
    return project


def get_teacher_projects(teacher, status: str | None = None):
    """
    Returns queryset of projects created by teacher, annotated with assignment count.
    Optionally filtered by status.
    """
    qs = Project.objects.filter(created_by=teacher).annotate(
        assignment_count=Count('assignments')
    ).order_by('-created_at')

    if status and status in ProjectStatus.values:
        qs = qs.filter(status=status)

    return qs


def get_teacher_project_or_404(project_id: int, teacher) -> Project:
    """
    Retrieves a project owned by the teacher or raises Http404.
    """
    try:
        return Project.objects.annotate(
            assignment_count=Count('assignments')
        ).get(pk=project_id, created_by=teacher)
    except Project.DoesNotExist:
        raise Http404("Project not found.")


def generate_project_report_data(project: Project, teacher) -> list[dict]:
    """
    Gathers report data for assigned students.
    Shows latest progress % and submission count (defensively returns '-' until those sprints).
    """
    if project.created_by_id != teacher.id:
        raise Http404("Project not found.")

    assignments = project.assignments.select_related('student').order_by('student__name')
    report_rows = []

    for assignment in assignments:
        # Check defensively if progress or submissions reverse relations exist
        latest_progress = "-"
        if hasattr(assignment, 'progress_updates') and assignment.progress_updates.exists():
            latest = assignment.progress_updates.order_by('-updated_on').first()
            latest_progress = f"{latest.percent_complete}%"

        submissions_count = "-"
        if hasattr(assignment, 'submissions') and assignment.submissions.exists():
            submissions_count = str(assignment.submissions.count())

        report_rows.append({
            'student_name': assignment.student.get_display_name(),
            'roll_no': assignment.student.roll_no or "-",
            'email': assignment.student.email,
            'department': assignment.student.department or "-",
            'status': assignment.get_status_display(),
            'assigned_on': assignment.assigned_on,
            'latest_progress': latest_progress,
            'submissions_count': submissions_count,
        })

    return report_rows


def generate_project_csv_report(project: Project, teacher) -> str:
    """
    Generates CSV string content for the project report.
    """
    data = generate_project_report_data(project, teacher)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        'Student Name',
        'Roll Number',
        'Email',
        'Department',
        'Assignment Status',
        'Assigned On',
        'Latest Progress',
        'Submissions Count'
    ])

    for row in data:
        writer.writerow([
            row['student_name'],
            row['roll_no'],
            row['email'],
            row['department'],
            row['status'],
            row['assigned_on'].strftime("%Y-%m-%d %H:%M"),
            row['latest_progress'],
            row['submissions_count']
        ])

    return output.getvalue()
