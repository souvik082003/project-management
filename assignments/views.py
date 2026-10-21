from django.contrib import messages
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render

from accounts.decorators import student_required, teacher_required
from projects import services as project_services

from . import services
from .models import AssignmentStatus

User = get_user_model()


@teacher_required
def assign_project_select_view(request):
    """
    Landing view for assignment management: lists teacher's projects with assign buttons.
    """
    projects = project_services.get_teacher_projects(request.user)
    return render(request, "assignments/assign_select.html", {"projects": projects})


@teacher_required
def assign_students_view(request, project_id: int):
    """
    Assigns one or more students to a specific project.
    Supports filtering students by name or roll number.
    Displays summary message of newly assigned vs already assigned.
    """
    project = project_services.get_teacher_project_or_404(project_id, request.user)

    search_query = request.GET.get("q", "").strip()
    students_qs = User.objects.filter(role="student")

    if search_query:
        students_qs = students_qs.filter(
            Q(name__icontains=search_query) | Q(roll_no__icontains=search_query) | Q(email__icontains=search_query)
        )

    students = students_qs.order_by("name")
    already_assigned_ids = set(project.assignments.values_list("student_id", flat=True))

    if request.method == "POST":
        student_ids = request.POST.getlist("student_ids")
        if not student_ids:
            messages.error(request, "Please select at least one student to assign.")
        else:
            try:
                assigned, skipped = services.assign_students_to_project(
                    teacher=request.user, project=project, student_ids=[int(s_id) for s_id in student_ids]
                )
                messages.success(request, f"{assigned} assigned, {skipped} already assigned.")
                return redirect("projects:project_detail", pk=project.id)
            except ValidationError as err:
                messages.error(request, err.messages[0] if hasattr(err, "messages") else str(err))

    return render(
        request,
        "assignments/assign_students.html",
        {
            "project": project,
            "students": students,
            "already_assigned_ids": already_assigned_ids,
            "search_query": search_query,
        },
    )


@student_required
def my_assignments_view(request):
    """
    Lists projects assigned to the logged-in student with status filter and pagination.
    """
    status_filter = request.GET.get("status", "").strip()
    assignments_qs = services.get_student_assignments(student=request.user, status=status_filter or None)

    paginator = Paginator(assignments_qs, 10)
    page_number = request.GET.get("page")
    page_obj = paginator.get_page(page_number)

    return render(
        request,
        "assignments/my_assignments.html",
        {
            "page_obj": page_obj,
            "status_filter": status_filter,
            "status_choices": AssignmentStatus.choices,
        },
    )


@student_required
def assignment_detail_view(request, pk: int):
    """
    Displays assignment details for the student.
    Includes the Update Progress form, Bootstrap progress bar, and history timeline.
    A student cannot open another student's assignment (returns 404).
    """
    from progress import services as progress_services
    from progress.forms import ProgressUpdateForm

    assignment = services.get_student_assignment_or_404(pk, request.user)
    history = assignment.progress_updates.all().order_by("-updated_on")
    latest_update = history.first()
    latest_percent = latest_update.percent_complete if latest_update else 0
    can_update = assignment.status in progress_services.ALLOWED_PROGRESS_STATUSES

    if request.method == "POST" and "update_progress" in request.POST:
        if not can_update:
            messages.error(
                request,
                f"Progress updates are locked because this project is currently '{assignment.get_status_display()}'.",
            )
            return redirect("assignments:assignment_detail", pk=assignment.id)

        form = ProgressUpdateForm(request.POST)
        if form.is_valid():
            try:
                progress_services.add_progress_update(
                    student=request.user,
                    assignment=assignment,
                    percent_complete=form.cleaned_data["percent_complete"],
                    remarks=form.cleaned_data["remarks"],
                )
                messages.success(request, "Progress updated successfully!")
                return redirect("assignments:assignment_detail", pk=assignment.id)
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
        "assignments/assignment_detail.html",
        {
            "assignment": assignment,
            "project": assignment.project,
            "form": form,
            "history": history,
            "latest_percent": latest_percent,
            "can_update": can_update,
        },
    )
