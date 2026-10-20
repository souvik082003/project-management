from django.contrib import admin
from .models import ProjectAssignment


@admin.register(ProjectAssignment)
class ProjectAssignmentAdmin(admin.ModelAdmin):
    list_display = ('project', 'student', 'status', 'assigned_on')
    list_filter = ('status', 'assigned_on')
    search_fields = ('project__title', 'student__name', 'student__email', 'student__roll_no')
