"""
Business logic service layer for reviews module.
Handles feedback giving, revision requests, mark assignment, grading rules,
marks reporting, and automated project closure transitions.
"""
import csv
import io
import logging
from decimal import Decimal
from django.conf import settings
from django.core.exceptions import ValidationError, PermissionDenied
from django.db import transaction
from django.http import Http404
from accounts.models import UserRole
from projects.models import Project, ProjectStatus
from projects import services as project_services
from assignments.models import ProjectAssignment, AssignmentStatus
from assignments import services as assignment_services
from submissions.models import Submission
from .models import Feedback, Marks, get_grade_band

logger = logging.getLogger('pms')


def notify_student_new_feedback(feedback: Feedback) -> None:
    """
    Notifies student of review feedback via email and in-app alert.
    Never lets notification failure break review submission.
    """
    try:
        from dashboard import notifications as dashboard_notifications
        dashboard_notifications.notify_feedback(feedback)
    except Exception as err:
        logger.warning(f"Feedback notification failed (non-blocking): {err}")


def notify_student_marks_assigned(marks: Marks) -> None:
    """
    Notifies student of published marks and grades via email and in-app alert.
    Never lets notification failure break marks saving.
    """
    try:
        from dashboard import notifications as dashboard_notifications
        dashboard_notifications.notify_marks(marks)
    except Exception as err:
        logger.warning(f"Marks notification failed (non-blocking): {err}")


def give_feedback(submission: Submission, teacher, comments: str, request_revision: bool = False) -> Feedback:
    """
    UC12 Give Feedback: allows a teacher to submit review feedback for a student submission.
    If request_revision is True, assignment transitions Under review -> Revision requested;
    otherwise it remains Under review.
    """
    if not getattr(teacher, 'is_teacher', False):
        raise PermissionDenied("Only teachers can submit review feedback.")

    assignment = submission.assignment
    if assignment.project.created_by_id != teacher.id:
        raise Http404("Submission does not belong to your supervised projects.")

    comments = (comments or "").strip()
    if not comments:
        raise ValidationError({"comments": "Feedback comments cannot be empty."})

    # If assignment is in Submitted state, transition to Under review first
    if assignment.status == AssignmentStatus.SUBMITTED:
        assignment_services.transition(assignment, AssignmentStatus.UNDER_REVIEW)

    if assignment.status != AssignmentStatus.UNDER_REVIEW:
        raise ValidationError(
            f"Feedback can only be given while assignment is under review (current status is '{assignment.get_status_display()}')."
        )

    with transaction.atomic():
        feedback = Feedback.objects.create(
            submission=submission,
            teacher=teacher,
            comments=comments,
            requested_revision=request_revision
        )

        if request_revision:
            assignment_services.transition(assignment, AssignmentStatus.REVISION_REQUESTED)

    # Non-blocking notification
    try:
        notify_student_new_feedback(feedback)
    except Exception as notify_err:
        logger.warning(f"Feedback notification failed (non-blocking): {notify_err}")

    logger.info(
        f"Feedback recorded for Submission {submission.id} by Teacher {teacher.email} "
        f"(Requested Revision={request_revision})"
    )
    return feedback


def assign_marks(assignment: ProjectAssignment, teacher, score, max_score=Decimal('100.00')) -> Marks:
    """
    UC14 Assign Marks: allows teacher to grade an assignment with score and max_score.
    Rules:
      - Teacher must be the project creator.
      - At least one submission must exist.
      - Assignment must be Under review (if grading initial) or Evaluated (if updating).
      - Editing allowed until Project is Closed.
      - Exactly one Marks record per assignment (updates existing on subsequent calls).
      - On save, assignment transitions to Evaluated.
      - When ALL assignments of the project are Evaluated, project transitions to Closed.
    """
    if not getattr(teacher, 'is_teacher', False):
        raise PermissionDenied("Only teachers can assign marks.")

    if assignment.project.created_by_id != teacher.id:
        raise Http404("Assignment does not belong to your supervised projects.")

    if assignment.project.status == ProjectStatus.CLOSED:
        raise ValidationError("Marks cannot be assigned or updated because the project is closed.")

    if assignment.submissions.count() == 0:
        raise ValidationError("Cannot assign marks without at least one submitted deliverable.")

    # Convert score and max_score to Decimal
    try:
        score_dec = Decimal(str(score))
    except Exception:
        raise ValidationError({"score": "Invalid numerical format for score."})

    try:
        max_score_dec = Decimal(str(max_score)) if max_score is not None else Decimal('100.00')
    except Exception:
        raise ValidationError({"max_score": "Invalid numerical format for max score."})

    if score_dec < Decimal('0.00'):
        raise ValidationError({"score": "Score cannot be negative."})

    if max_score_dec <= Decimal('0.00'):
        raise ValidationError({"max_score": "Max score must be greater than zero."})

    if score_dec > max_score_dec:
        raise ValidationError({"score": "Score cannot exceed maximum score."})

    # Validate assignment status
    if assignment.status not in [AssignmentStatus.UNDER_REVIEW, AssignmentStatus.EVALUATED]:
        raise ValidationError(
            f"Assignment must be under review to assign marks (current status is '{assignment.get_status_display()}')."
        )

    with transaction.atomic():
        existing_marks = Marks.objects.filter(assignment=assignment).first()
        if existing_marks:
            existing_marks.score = score_dec
            existing_marks.max_score = max_score_dec
            existing_marks.teacher = teacher
            existing_marks.full_clean()
            existing_marks.save()
            marks = existing_marks
        else:
            marks = Marks(
                assignment=assignment,
                teacher=teacher,
                score=score_dec,
                max_score=max_score_dec
            )
            marks.full_clean()
            marks.save()

        # State transition: Under review -> Evaluated
        if assignment.status == AssignmentStatus.UNDER_REVIEW:
            assignment_services.transition(assignment, AssignmentStatus.EVALUATED)

        # Check if all assignments for this project are now Evaluated
        project = assignment.project
        total_assignments = project.assignments.count()
        evaluated_count = project.assignments.filter(status=AssignmentStatus.EVALUATED).count()

        if total_assignments > 0 and evaluated_count == total_assignments:
            if project.status == ProjectStatus.ASSIGNED:
                project_services.transition(project, ProjectStatus.CLOSED)

    # Non-blocking notification
    try:
        notify_student_marks_assigned(marks)
    except Exception as notify_err:
        logger.warning(f"Marks notification failed (non-blocking): {notify_err}")

    logger.info(
        f"Marks assigned for Assignment {assignment.id}: {marks.score}/{marks.max_score} "
        f"by Teacher {teacher.email}"
    )
    return marks


def get_student_feedbacks(user, assignment_id: int = None):
    """
    UC13 View Feedback: retrieves feedbacks for student's own submissions,
    newest first, grouped by submission version.
    """
    if not getattr(user, 'is_student', False):
        raise PermissionDenied("Only students can access student feedback view.")

    qs = Feedback.objects.filter(
        submission__assignment__student=user
    ).select_related(
        'submission', 'submission__assignment', 'submission__assignment__project', 'teacher'
    ).order_by('-submission__version', '-given_on')

    if assignment_id:
        # Verify ownership
        if not ProjectAssignment.objects.filter(id=assignment_id, student=user).exists():
            raise Http404("Assignment not found.")
        qs = qs.filter(submission__assignment_id=assignment_id)

    return qs


def get_student_marks(user, assignment_id: int = None):
    """
    UC15 View Marks: returns marks for student's assignments, visible ONLY once Evaluated.
    """
    if not getattr(user, 'is_student', False):
        raise PermissionDenied("Only students can access student marks view.")

    qs = Marks.objects.filter(
        assignment__student=user,
        assignment__status=AssignmentStatus.EVALUATED
    ).select_related('assignment', 'assignment__project', 'teacher').order_by('-graded_on')

    if assignment_id:
        try:
            assignment = ProjectAssignment.objects.get(id=assignment_id, student=user)
        except ProjectAssignment.DoesNotExist:
            raise Http404("Assignment not found.")

        if assignment.status != AssignmentStatus.EVALUATED:
            raise Http404("Marks have not been published for this project yet.")

        marks = qs.filter(assignment=assignment).first()
        if not marks:
            raise Http404("Marks record not found.")
        return marks

    return qs


def get_project_marks_report(project: Project, teacher) -> dict:
    """
    UC16 Generate Marks Report: returns structured per-project report data
    including all student records, scores, grade bands, and statistical summaries.
    """
    if project.created_by_id != teacher.id:
        raise Http404("Project does not belong to your supervised projects.")

    passing_pct = getattr(settings, 'PMS_PASSING_PERCENTAGE', 40.0)

    assignments = project.assignments.select_related('student', 'marks').order_by('student__name')

    records = []
    percentages = []
    passing_count = 0
    failing_count = 0

    for assign in assignments:
        has_marks = hasattr(assign, 'marks') and assign.marks is not None
        if has_marks:
            marks_obj = assign.marks
            pct = marks_obj.percentage
            percentages.append(pct)
            is_pass = marks_obj.is_pass
            if is_pass:
                passing_count += 1
            else:
                failing_count += 1

            records.append({
                'assignment': assign,
                'student': assign.student,
                'has_marks': True,
                'marks': marks_obj,
                'score': marks_obj.score,
                'max_score': marks_obj.max_score,
                'percentage': pct,
                'grade_band': marks_obj.grade_band,
                'is_pass': is_pass,
                'status': assign.get_status_display(),
            })
        else:
            records.append({
                'assignment': assign,
                'student': assign.student,
                'has_marks': False,
                'marks': None,
                'score': None,
                'max_score': None,
                'percentage': None,
                'grade_band': 'N/A',
                'is_pass': None,
                'status': assign.get_status_display(),
            })

    total_count = assignments.count()
    evaluated_count = len(percentages)

    if percentages:
        avg_pct = round(sum(percentages) / len(percentages), 2)
        highest_pct = round(max(percentages), 2)
        lowest_pct = round(min(percentages), 2)
    else:
        avg_pct = None
        highest_pct = None
        lowest_pct = None

    stats = {
        'total_students': total_count,
        'evaluated_count': evaluated_count,
        'pending_count': total_count - evaluated_count,
        'average_percentage': avg_pct,
        'highest_percentage': highest_pct,
        'lowest_percentage': lowest_pct,
        'passing_count': passing_count,
        'failing_count': failing_count,
        'passing_percentage_threshold': passing_pct,
    }

    return {
        'project': project,
        'records': records,
        'stats': stats,
    }


def generate_marks_csv(project: Project, teacher) -> str:
    """
    Exports project evaluation marks report as CSV formatted text.
    """
    report_data = get_project_marks_report(project, teacher)
    output = io.StringIO()
    writer = csv.writer(output)

    # Header metadata
    writer.writerow(["Academic Project Management System - Marks Report"])
    writer.writerow(["Project Title", project.title])
    writer.writerow(["Supervisor", teacher.get_display_name()])
    writer.writerow(["Project Status", project.get_status_display()])
    writer.writerow([])

    # Table columns
    writer.writerow([
        "Student Name",
        "Roll Number",
        "Department",
        "Assignment Status",
        "Score",
        "Max Score",
        "Percentage",
        "Grade Band",
        "Result"
    ])

    for rec in report_data['records']:
        student = rec['student']
        if rec['has_marks']:
            writer.writerow([
                student.name,
                student.roll_no or "-",
                student.department or "-",
                rec['status'],
                rec['score'],
                rec['max_score'],
                f"{rec['percentage']}%",
                rec['grade_band'],
                "PASS" if rec['is_pass'] else "FAIL"
            ])
        else:
            writer.writerow([
                student.name,
                student.roll_no or "-",
                student.department or "-",
                rec['status'],
                "-",
                "-",
                "-",
                "N/A",
                "PENDING"
            ])

    writer.writerow([])
    writer.writerow(["Summary Statistics"])
    stats = report_data['stats']
    writer.writerow(["Total Assigned Students", stats['total_students']])
    writer.writerow(["Evaluated Students", stats['evaluated_count']])
    writer.writerow(["Pending Evaluation", stats['pending_count']])
    writer.writerow(["Average Percentage", f"{stats['average_percentage']}%" if stats['average_percentage'] is not None else "N/A"])
    writer.writerow(["Highest Percentage", f"{stats['highest_percentage']}%" if stats['highest_percentage'] is not None else "N/A"])
    writer.writerow(["Lowest Percentage", f"{stats['lowest_percentage']}%" if stats['lowest_percentage'] is not None else "N/A"])
    writer.writerow(["Passed Students", stats['passing_count']])
    writer.writerow(["Failed Students", stats['failing_count']])

    return output.getvalue()
