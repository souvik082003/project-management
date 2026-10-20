from django.contrib import admin
from .models import Submission


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'version', 'file_name', 'file_size', 'submitted_on')
    list_filter = ('version', 'submitted_on')
    search_fields = ('assignment__student__name', 'assignment__project__title', 'file_name')
