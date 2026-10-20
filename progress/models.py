from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator


class ProgressUpdate(models.Model):
    assignment = models.ForeignKey(
        'assignments.ProjectAssignment',
        on_delete=models.CASCADE,
        related_name='progress_updates'
    )
    percent_complete = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0), MaxValueValidator(100)],
        verbose_name="Percent Complete"
    )
    remarks = models.TextField(blank=True, verbose_name="Remarks")
    updated_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-updated_on']

    def __str__(self):
        return f"{self.assignment.student.get_display_name()} - {self.percent_complete}% ({self.updated_on.strftime('%Y-%m-%d')})"
