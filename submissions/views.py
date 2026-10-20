from django.shortcuts import render, redirect
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import FileResponse, Http404
from django.contrib.auth.decorators import login_required
from accounts.decorators import student_required, teacher_required
from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from projects import services as project_services
from .models import Submission
from .forms import SubmissionForm
from . import services


@student_required
def student_upload_picker_view(request):
    """
    Landing view for /submissions/upload/.
    Redirects to the upload view if student has one project, or displays picker list.
    """
    assignments = assignment_services.get_student_assignments(request.user)
    if assignments.count() == 1:
        return redirect('submissions:upload_submission', assignment_id=assignments.first().id)
    return render(request, 'submissions/student_upload_picker.html', {'assignments': assignments})


@student_required
def upload_submission_view(request, assignment_id: int):
    """
    UC10 Submit File: allows a student to upload a new version of their project work.
    """
    assignment = assignment_services.get_student_assignment_or_404(assignment_id, request.user)
    can_submit = assignment.status in services.ALLOWED_SUBMISSION_STATUSES
    submission_history = assignment.submissions.all().order_by('-version')

    if request.method == 'POST':
        if not can_submit:
            messages.error(
                request,
                f"Submissions are currently locked because status is '{assignment.get_status_display()}'."
            )
            return redirect('assignments:assignment_detail', pk=assignment.id)

        form = SubmissionForm(request.POST, request.FILES)
        if form.is_valid():
            try:
                submission = services.submit_file(
                    assignment=assignment,
                    uploaded_file=request.FILES['file'],
                    user=request.user
                )
                messages.success(
                    request,
                    f"Successfully uploaded '{submission.file_name}' as Version {submission.version}!"
                )
                return redirect('submissions:upload_submission', assignment_id=assignment.id)
            except ValidationError as err:
                if hasattr(err, 'message_dict'):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = SubmissionForm()

    return render(request, 'submissions/upload_submission.html', {
        'assignment': assignment,
        'form': form,
        'can_submit': can_submit,
        'submission_history': submission_history,
    })


@teacher_required
def teacher_submissions_list_view(request):
    """
    UC11 View Submissions: lists all submissions across teacher's projects with filter & late badges.
    """
    project_id = request.GET.get('project', '').strip()
    status_filter = request.GET.get('status', '').strip()

    teacher_projects = project_services.get_teacher_projects(request.user)

    submissions_qs = Submission.objects.filter(
        assignment__project__created_by=request.user
    ).select_related('assignment', 'assignment__project', 'assignment__student').order_by('-submitted_on')

    if project_id and project_id.isdigit():
        submissions_qs = submissions_qs.filter(assignment__project_id=int(project_id))

    if status_filter:
        submissions_qs = submissions_qs.filter(assignment__status=status_filter)

    return render(request, 'submissions/teacher_submission_list.html', {
        'submissions': submissions_qs,
        'teacher_projects': teacher_projects,
        'selected_project_id': int(project_id) if project_id and project_id.isdigit() else None,
        'status_filter': status_filter,
        'status_choices': AssignmentStatus.choices,
    })


@teacher_required
def teacher_submission_detail_view(request, submission_id: int):
    """
    Teacher opens submission. Automatically transitions assignment Submitted -> Under review.
    """
    try:
        submission = Submission.objects.select_related(
            'assignment', 'assignment__project', 'assignment__student'
        ).get(pk=submission_id, assignment__project__created_by=request.user)
    except Submission.DoesNotExist:
        raise Http404("Submission not found.")

    # Execute transition Submitted -> Under review on first opening
    services.teacher_open_submission(submission, request.user)

    all_versions = submission.assignment.submissions.all().order_by('-version')

    return render(request, 'submissions/teacher_submission_detail.html', {
        'submission': submission,
        'all_versions': all_versions,
    })


@login_required
def download_submission_view(request, submission_id: int):
    """
    Secure file download view for submitted work.
    Verifies that the requester is either the owning student or the supervising teacher.
    """
    submission, full_path = services.get_submission_for_download(submission_id, request.user)

    return FileResponse(
        open(full_path, 'rb'),
        as_attachment=True,
        filename=submission.file_name
    )
