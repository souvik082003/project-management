import os

from django.db import models


class Submission(models.Model):
    assignment = models.ForeignKey(
        "assignments.ProjectAssignment", on_delete=models.CASCADE, related_name="submissions"
    )
    file_path = models.CharField(max_length=500, verbose_name="Storage Path")
    file_name = models.CharField(max_length=255, verbose_name="File Name")
    file_size = models.PositiveBigIntegerField(verbose_name="File Size (bytes)")
    version = models.PositiveIntegerField(default=1, verbose_name="Version")
    submitted_on = models.DateTimeField(auto_now_add=True, verbose_name="Submitted On")

    class Meta:
        ordering = ["-version", "-submitted_on"]

    @property
    def is_late(self) -> bool:
        """Returns True if the submission timestamp is past the project's deadline."""
        return self.submitted_on > self.assignment.project.deadline

    @property
    def formatted_size(self) -> str:
        """Human-readable file size representation."""
        if self.file_size < 1024:
            return f"{self.file_size} B"
        elif self.file_size < 1024 * 1024:
            return f"{round(self.file_size / 1024, 1)} KB"
        else:
            return f"{round(self.file_size / (1024 * 1024), 2)} MB"

    @property
    def extension(self) -> str:
        """Returns lowercase file extension without dot."""
        return os.path.splitext(self.file_name)[1].lower().lstrip(".")

    def __str__(self):
        return f"{self.assignment.project.title} - {self.assignment.student.get_display_name()} v{self.version}"
