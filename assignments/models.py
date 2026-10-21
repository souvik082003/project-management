from django.db import models
from django.conf import settings
from django.utils import timezone


class AssignmentStatus(models.TextChoices):
    ASSIGNED = 'Assigned', 'Assigned'
    IN_PROGRESS = 'In progress', 'In progress'
    OVERDUE = 'Overdue', 'Overdue'
    SUBMITTED = 'Submitted', 'Submitted'
    UNDER_REVIEW = 'Under review', 'Under review'
    REVISION_REQUESTED = 'Revision requested', 'Revision requested'
    EVALUATED = 'Evaluated', 'Evaluated'


class ProjectAssignment(models.Model):
    project = models.ForeignKey(
        'projects.Project',
        on_delete=models.CASCADE,
        related_name='assignments'
    )
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='project_assignments'
    )
    assigned_on = models.DateTimeField(auto_now_add=True)
    status = models.CharField(
        max_length=30,
        choices=AssignmentStatus.choices,
        default=AssignmentStatus.ASSIGNED
    )
    deadline_reminder_sent = models.BooleanField(default=False, verbose_name="Deadline Reminder Sent")

    class Meta:
        ordering = ['-assigned_on']
        unique_together = ('project', 'student')

    @property
    def days_remaining(self):
        """Returns days remaining until project deadline (0 if deadline passed)."""
        now = timezone.now()
        if self.project.deadline > now:
            delta = self.project.deadline - now
            return delta.days
        return 0

    @property
    def is_past_deadline(self):
        return timezone.now() > self.project.deadline

    def __str__(self):
        return f"{self.project.title} -> {self.student.get_display_name()} [{self.status}]"
