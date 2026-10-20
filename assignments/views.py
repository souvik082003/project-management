from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Q
from django.contrib.auth import get_user_model
from accounts.decorators import teacher_required, student_required
from projects import services as project_services
from .models import AssignmentStatus, ProjectAssignment
from . import services

User = get_user_model()


@teacher_required
def assign_project_select_view(request):
    """
    Landing view for assignment management: lists teacher's projects with assign buttons.
    """
    projects = project_services.get_teacher_projects(request.user)
    return render(request, 'assignments/assign_select.html', {'projects': projects})


@teacher_required
def assign_students_view(request, project_id: int):
    """
    Assigns one or more students to a specific project.
    Supports filtering students by name or roll number.
    Displays summary message of newly assigned vs already assigned.
    """
    project = project_services.get_teacher_project_or_404(project_id, request.user)

    search_query = request.GET.get('q', '').strip()
    students_qs = User.objects.filter(role='student')

    if search_query:
        students_qs = students_qs.filter(
            Q(name__icontains=search_query) |
            Q(roll_no__icontains=search_query) |
            Q(email__icontains=search_query)
        )

    students = students_qs.order_by('name')
    already_assigned_ids = set(
        project.assignments.values_list('student_id', flat=True)
    )

    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        if not student_ids:
            messages.error(request, "Please select at least one student to assign.")
        else:
            try:
                assigned, skipped = services.assign_students_to_project(
                    teacher=request.user,
                    project=project,
                    student_ids=[int(s_id) for s_id in student_ids]
                )
                messages.success(request, f"{assigned} assigned, {skipped} already assigned.")
                return redirect('projects:project_detail', pk=project.id)
            except ValidationError as err:
                messages.error(request, err.messages[0] if hasattr(err, 'messages') else str(err))

    return render(request, 'assignments/assign_students.html', {
        'project': project,
        'students': students,
        'already_assigned_ids': already_assigned_ids,
        'search_query': search_query,
    })


@student_required
def my_assignments_view(request):
    """
    Lists projects assigned to the logged-in student with status filter and pagination.
    """
    status_filter = request.GET.get('status', '').strip()
    assignments_qs = services.get_student_assignments(
        student=request.user,
        status=status_filter or None
    )

    paginator = Paginator(assignments_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'assignments/my_assignments.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': AssignmentStatus.choices,
    })


@student_required
def assignment_detail_view(request, pk: int):
    """
    Displays assignment details for the student.
    A student cannot open another student's assignment (returns 404).
    """
    assignment = services.get_student_assignment_or_404(pk, request.user)

    return render(request, 'assignments/assignment_detail.html', {
        'assignment': assignment,
        'project': assignment.project,
    })
