from django.shortcuts import render, redirect
from django.core.paginator import Paginator
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponse
from accounts.decorators import teacher_required
from .forms import ProjectForm
from .models import ProjectStatus
from . import services


@teacher_required
def project_list_view(request):
    """
    Lists projects created by the logged-in teacher with status filter and pagination.
    """
    status_filter = request.GET.get('status', '').strip()
    projects_qs = services.get_teacher_projects(request.user, status=status_filter or None)

    paginator = Paginator(projects_qs, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'projects/project_list.html', {
        'page_obj': page_obj,
        'status_filter': status_filter,
        'status_choices': ProjectStatus.choices,
    })


@teacher_required
def project_create_view(request):
    """
    Creates a new project in Draft status.
    """
    if request.method == 'POST':
        form = ProjectForm(request.POST)
        if form.is_valid():
            try:
                project = services.create_project(
                    teacher=request.user,
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data['description'],
                    deadline=form.cleaned_data['deadline']
                )
                messages.success(request, f"Project '{project.title}' created successfully.")
                return redirect('projects:project_list')
            except ValidationError as err:
                if hasattr(err, 'message_dict'):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = ProjectForm()

    return render(request, 'projects/project_form.html', {
        'form': form,
        'action': 'Create',
    })


@teacher_required
def project_edit_view(request, pk: int):
    """
    Edits an existing project owned by the logged-in teacher.
    Raises 404 if project belongs to another teacher.
    """
    project = services.get_teacher_project_or_404(pk, request.user)

    if request.method == 'POST':
        form = ProjectForm(request.POST, instance=project)
        if form.is_valid():
            try:
                services.update_project(
                    project=project,
                    teacher=request.user,
                    title=form.cleaned_data['title'],
                    description=form.cleaned_data['description'],
                    deadline=form.cleaned_data['deadline']
                )
                messages.success(request, f"Project '{project.title}' updated successfully.")
                return redirect('projects:project_list')
            except ValidationError as err:
                if hasattr(err, 'message_dict'):
                    for field, err_list in err.message_dict.items():
                        for msg in err_list:
                            form.add_error(field if field in form.fields else None, msg)
                else:
                    for msg in err.messages:
                        form.add_error(None, msg)
    else:
        form = ProjectForm(instance=project)

    return render(request, 'projects/project_form.html', {
        'form': form,
        'project': project,
        'action': 'Edit',
    })


@teacher_required
def project_detail_view(request, pk: int):
    """
    Views project overview and assigned students list.
    """
    project = services.get_teacher_project_or_404(pk, request.user)
    assignments = project.assignments.select_related('student').order_by('-assigned_on')

    return render(request, 'projects/project_detail.html', {
        'project': project,
        'assignments': assignments,
    })


@teacher_required
def project_report_view(request, pk: int):
    """
    Displays the project evaluation and monitoring report.
    Supports print-friendly rendering.
    """
    project = services.get_teacher_project_or_404(pk, request.user)
    report_rows = services.generate_project_report_data(project, request.user)

    return render(request, 'projects/project_report.html', {
        'project': project,
        'report_rows': report_rows,
        'is_print': request.GET.get('print') == '1',
    })


@teacher_required
def project_report_csv_view(request, pk: int):
    """
    Downloads CSV report of assigned students and progress.
    """
    project = services.get_teacher_project_or_404(pk, request.user)
    csv_content = services.generate_project_csv_report(project, request.user)

    response = HttpResponse(csv_content, content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="project_{project.id}_report.csv"'
    return response
