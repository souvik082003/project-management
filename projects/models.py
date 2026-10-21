from django.conf import settings
from django.db import models
from django.utils import timezone


class ProjectStatus(models.TextChoices):
    DRAFT = "Draft", "Draft"
    ASSIGNED = "Assigned", "Assigned"
    CLOSED = "Closed", "Closed"


class Project(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=ProjectStatus.choices, default=ProjectStatus.DRAFT, db_index=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="created_projects")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def is_past_deadline(self, now=None):
        current_time = now or timezone.now()
        return self.deadline < current_time

    @property
    def is_draft(self):
        return self.status == ProjectStatus.DRAFT

    @property
    def is_assigned(self):
        return self.status == ProjectStatus.ASSIGNED

    @property
    def is_closed(self):
        return self.status == ProjectStatus.CLOSED

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"
