from django.contrib import admin

from .models import Feedback, Marks


@admin.register(Feedback)
class FeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "submission", "teacher", "requested_revision", "given_on")
    list_filter = ("requested_revision", "given_on")
    search_fields = ("submission__file_name", "comments", "teacher__name", "teacher__email")
    raw_id_fields = ("submission", "teacher")


@admin.register(Marks)
class MarksAdmin(admin.ModelAdmin):
    list_display = ("id", "assignment", "teacher", "score", "max_score", "percentage", "grade_band", "graded_on")
    list_filter = ("graded_on",)
    search_fields = ("assignment__student__name", "assignment__project__title", "teacher__name")
    raw_id_fields = ("assignment", "teacher")
