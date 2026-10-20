from django.contrib import admin
from .models import ProgressUpdate


@admin.register(ProgressUpdate)
class ProgressUpdateAdmin(admin.ModelAdmin):
    list_display = ('assignment', 'percent_complete', 'updated_on')
    list_filter = ('updated_on', 'percent_complete')
    search_fields = ('assignment__student__name', 'assignment__project__title', 'remarks')
