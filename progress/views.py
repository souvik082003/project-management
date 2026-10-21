from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import Http404, HttpResponse
from django.shortcuts import redirect, render

from accounts.decorators import student_required, teacher_required
from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from projects import services as project_services

from . import services
from .forms import ProgressUpdateForm


@student_required
def student_progress_list_view(request):
    """
    Landing view for /progress/update/.
    Redirects to student's assignment if only one exists, or lists assignments to pick.
    """
    assignments = assignment_services.get_student_assignments(request.user)
    if assignments.count() == 1:
        return redirect("progress:update_progress", assignment_id=assignments.first().id)
    return render(request, "progress/student_assignment_picker.html", {"assignments": assignments})


@student_required
def update_progress_view(request, assignment_id: int):
    """
    UC07 Update Progress: student submits percentage and remarks.
    Displays progress bar and historical updates timeline.
    """
    assignment = assignment_services.get_student_assignment_or_404(assignment_id, request.user)
    history = assignment.progress_updates.all().order_by("-updated_on")
    latest_update = history.first()
    latest_percent = latest_update.percent_complete if latest_update else 0

    can_update = assignment.status in services.ALLOWED_PROGRESS_STATUSES

    if request.method == "POST":
        if not can_update:
            messages.error(
                request,
                f"Progress updates are locked because this project is currently '{assignment.get_status_display()}'.",
            )
            return redirect("assignments:assignment_detail", pk=assignment.id)

        form = ProgressUpdateForm(request.POST)
        if form.is_valid():
            try:
                services.add_progress_update(
                    student=request.user,
                    assignment=assignment,
                    percent_complete=form.cleaned_data["percent_complete"],
                    remarks=form.cleaned_data["remarks"],
                )
                messages.success(request, "Progress update saved successfully!")
                return redirect("progress:update_progress", assignment_id=assignment.id)
            except ValidationError as err:
                if hasattr(err, "message_dict"):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = ProgressUpdateForm(initial={"percent_complete": latest_percent})

    return render(
        request,
        "progress/update_progress.html",
        {
            "assignment": assignment,
            "form": form,
            "history": history,
            "latest_percent": latest_percent,
            "can_update": can_update,
        },
    )


@teacher_required
def monitor_progress_view(request):
    """
    UC08 Monitor Progress: teacher monitors student progress across projects.
    Filters by project and status. Highlights overdue rows (red) and stale updates (amber).
    """
    project_id = request.GET.get("project", "").strip()
    status_filter = request.GET.get("status", "").strip()

    teacher_projects = project_services.get_teacher_projects(request.user)

    selected_project_id = int(project_id) if project_id and project_id.isdigit() else None
    summary_items = services.get_progress_summary(
        teacher=request.user, project_id=selected_project_id, status=status_filter or None
    )

    return render(
        request,
        "progress/monitor_progress.html",
        {
            "summary_items": summary_items,
            "teacher_projects": teacher_projects,
            "selected_project_id": selected_project_id,
            "status_filter": status_filter,
            "status_choices": AssignmentStatus.choices,
        },
    )


@teacher_required
def assignment_progress_history_view(request, assignment_id: int):
    """
    Views history timeline of a student's progress updates for a teacher's project.
    """
    try:
        assignment = ProjectAssignment.objects.select_related("project", "student").get(
            pk=assignment_id, project__created_by=request.user
        )
    except ProjectAssignment.DoesNotExist:
        raise Http404("Assignment not found.")

    history = assignment.progress_updates.all().order_by("-updated_on")
    latest_update = history.first()
    latest_percent = latest_update.percent_complete if latest_update else 0

    return render(
        request,
        "progress/progress_history.html",
        {
            "assignment": assignment,
            "history": history,
            "latest_percent": latest_percent,
        },
    )


@teacher_required
def progress_report_select_view(request):
    """
    Landing page for progress reports: list teacher projects to generate report.
    """
    projects = project_services.get_teacher_projects(request.user)
    return render(request, "progress/report_select.html", {"projects": projects})


@teacher_required
def progress_report_view(request, project_id: int):
    """
    UC09 Generate Progress Report: per-project report with averages and overdue counts.
    Supports print-friendly rendering.
    """
    report = services.get_project_progress_report(request.user, project_id)

    return render(
        request,
        "progress/progress_report.html",
        {
            "project": report["project"],
            "summary_items": report["summary_items"],
            "total_students": report["total_students"],
            "avg_completion": report["avg_completion"],
            "overdue_count": report["overdue_count"],
            "is_print": request.GET.get("print") == "1",
        },
    )


@teacher_required
def progress_report_csv_view(request, project_id: int):
    """
    Downloads CSV progress report for a project.
    """
    csv_content = services.generate_progress_csv_report(request.user, project_id)

    response = HttpResponse(csv_content, content_type="text/csv")
    response["Content-Disposition"] = f'attachment; filename="project_{project_id}_progress_report.csv"'
    return response
