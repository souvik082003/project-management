from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.text import slugify

from accounts.decorators import student_required, teacher_required
from assignments.models import AssignmentStatus, ProjectAssignment
from projects import services as project_services
from projects.models import Project, ProjectStatus
from submissions.models import Submission

from . import services
from .forms import FeedbackForm, MarksForm
from .models import Feedback


@teacher_required
def reviews_dashboard_view(request):
    """
    Teacher landing dashboard for reviews & grading.
    Lists supervised projects with count of submissions needing review or evaluation.
    """
    from django.db.models import Count, Q

    projects = project_services.get_teacher_projects(request.user).annotate(
        total_assign=Count("assignments", distinct=True),
        evaluated_assign=Count("assignments", filter=Q(assignments__status=AssignmentStatus.EVALUATED), distinct=True),
        under_review_assign=Count(
            "assignments", filter=Q(assignments__status=AssignmentStatus.UNDER_REVIEW), distinct=True
        ),
        submitted_assign=Count("assignments", filter=Q(assignments__status=AssignmentStatus.SUBMITTED), distinct=True),
    )

    project_cards = []
    for p in projects:
        project_cards.append(
            {
                "project": p,
                "total_students": p.total_assign,
                "evaluated": p.evaluated_assign,
                "under_review": p.under_review_assign,
                "submitted": p.submitted_assign,
                "is_fully_evaluated": p.total_assign > 0 and p.total_assign == p.evaluated_assign,
            }
        )

    return render(
        request,
        "reviews/teacher_reviews_dashboard.html",
        {
            "project_cards": project_cards,
        },
    )


@teacher_required
def give_feedback_view(request, submission_id: int):
    """
    UC12 Give Feedback: Review page for teacher with student, project, progress history,
    submission download, previous feedback, and feedback form with 'Request revision'.
    """
    submission = get_object_or_404(
        Submission.objects.select_related("assignment", "assignment__project", "assignment__student"), pk=submission_id
    )

    if submission.assignment.project.created_by_id != request.user.id:
        raise Http404("Submission does not belong to your supervised projects.")

    assignment = submission.assignment
    progress_history = assignment.progress_updates.all().order_by("-updated_on")
    previous_feedbacks = (
        Feedback.objects.filter(submission__assignment=assignment)
        .select_related("submission", "teacher")
        .order_by("-given_on")
    )

    if request.method == "POST":
        form = FeedbackForm(request.POST)
        if form.is_valid():
            try:
                feedback = services.give_feedback(
                    submission=submission,
                    teacher=request.user,
                    comments=form.cleaned_data["comments"],
                    request_revision=form.cleaned_data["requested_revision"],
                )
                if feedback.requested_revision:
                    messages.warning(
                        request, "Feedback recorded with Revision Requested. Status changed to 'Revision requested'."
                    )
                else:
                    messages.success(request, "Feedback recorded successfully! Assignment remains Under review.")
                return redirect("reviews:give_feedback", submission_id=submission.id)
            except ValidationError as err:
                if hasattr(err, "message_dict"):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = FeedbackForm()

    return render(
        request,
        "reviews/give_feedback.html",
        {
            "submission": submission,
            "assignment": assignment,
            "progress_history": progress_history,
            "previous_feedbacks": previous_feedbacks,
            "form": form,
        },
    )


@teacher_required
def assign_marks_view(request, assignment_id: int):
    """
    UC14 Assign Marks: Allows teacher to grade an assignment with score and max_score.
    Allowed only if at least one submission exists and assignment is Under review or Evaluated.
    """
    assignment = get_object_or_404(ProjectAssignment.objects.select_related("project", "student"), pk=assignment_id)

    if assignment.project.created_by_id != request.user.id:
        raise Http404("Assignment does not belong to your supervised projects.")

    existing_marks = getattr(assignment, "marks", None)
    submissions = assignment.submissions.all().order_by("-version")

    if request.method == "POST":
        form = MarksForm(request.POST, instance=existing_marks)
        if form.is_valid():
            try:
                marks = services.assign_marks(
                    assignment=assignment,
                    teacher=request.user,
                    score=form.cleaned_data["score"],
                    max_score=form.cleaned_data["max_score"],
                )
                messages.success(
                    request,
                    f"Marks successfully recorded for {assignment.student.get_display_name()}: "
                    f"{marks.score}/{marks.max_score} ({marks.percentage}%, Grade {marks.grade_band})!",
                )
                return redirect("reviews:assign_marks", assignment_id=assignment.id)
            except ValidationError as err:
                if hasattr(err, "message_dict"):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = MarksForm(instance=existing_marks)

    return render(
        request,
        "reviews/assign_marks.html",
        {
            "assignment": assignment,
            "submissions": submissions,
            "existing_marks": existing_marks,
            "form": form,
            "can_grade": submissions.exists() and assignment.project.status != ProjectStatus.CLOSED,
        },
    )


@teacher_required
def marks_report_view(request, project_id: int):
    """
    UC16 Generate Marks Report: Per-project evaluation table with statistics, print styling,
    and CSV export link.
    """
    project = get_object_or_404(Project, pk=project_id, created_by=request.user)
    report_data = services.get_project_marks_report(project, request.user)

    return render(
        request,
        "reviews/marks_report.html",
        {
            "project": project,
            "records": report_data["records"],
            "stats": report_data["stats"],
        },
    )


@teacher_required
def marks_report_csv_view(request, project_id: int):
    """
    UC16 CSV export of project evaluation report.
    """
    project = get_object_or_404(Project, pk=project_id, created_by=request.user)
    csv_content = services.generate_marks_csv(project, request.user)

    filename = f"{slugify(project.title)}_marks_report.csv"
    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


@student_required
def student_feedback_list_view(request):
    """
    UC13 View Feedback (student): Lists all feedback received across assigned projects,
    grouped by submission version, newest first.
    """
    feedbacks = services.get_student_feedbacks(request.user)
    assignments = ProjectAssignment.objects.filter(student=request.user).select_related("project")

    return render(
        request,
        "reviews/student_feedback_list.html",
        {
            "feedbacks": feedbacks,
            "assignments": assignments,
        },
    )


@student_required
def student_assignment_feedback_view(request, assignment_id: int):
    """
    UC13 View Feedback for a specific assignment.
    """
    assignment = get_object_or_404(ProjectAssignment, pk=assignment_id, student=request.user)
    feedbacks = services.get_student_feedbacks(request.user, assignment_id=assignment.id)

    return render(
        request,
        "reviews/student_assignment_feedback.html",
        {
            "assignment": assignment,
            "feedbacks": feedbacks,
        },
    )


@student_required
def student_marks_list_view(request):
    """
    UC15 View Marks (student): Shows marks with percentage and pass/fail hint,
    visible ONLY once assignments are Evaluated.
    """
    marks_list = services.get_student_marks(request.user)
    assignments = ProjectAssignment.objects.filter(student=request.user).select_related("project")

    return render(
        request,
        "reviews/student_marks_list.html",
        {
            "marks_list": marks_list,
            "assignments": assignments,
        },
    )


@student_required
def student_view_marks_view(request, assignment_id: int):
    """
    UC15 View Marks for a specific assignment. Visible only once Evaluated.
    """
    marks = services.get_student_marks(request.user, assignment_id=assignment_id)

    return render(
        request,
        "reviews/student_view_marks.html",
        {
            "marks": marks,
            "assignment": marks.assignment,
        },
    )
