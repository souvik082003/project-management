from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


def get_grade_band(percentage: float) -> str:
    """Helper returning academic grade band from percentage."""
    if percentage >= 80.0:
        return "A"
    elif percentage >= 70.0:
        return "B"
    elif percentage >= 60.0:
        return "C"
    elif percentage >= 50.0:
        return "D"
    elif percentage >= 40.0:
        return "E"
    else:
        return "F"


class Feedback(models.Model):
    submission = models.ForeignKey(
        "submissions.Submission", on_delete=models.CASCADE, related_name="feedbacks", verbose_name="Submission"
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="given_feedbacks", verbose_name="Teacher"
    )
    comments = models.TextField(verbose_name="Feedback Comments")
    requested_revision = models.BooleanField(default=False, verbose_name="Revision Requested")
    given_on = models.DateTimeField(auto_now_add=True, verbose_name="Given On")

    class Meta:
        ordering = ["-given_on"]
        verbose_name = "Feedback"
        verbose_name_plural = "Feedbacks"

    def __str__(self):
        return f"Feedback for {self.submission} by {self.teacher.get_display_name()}"


class Marks(models.Model):
    assignment = models.OneToOneField(
        "assignments.ProjectAssignment",
        on_delete=models.CASCADE,
        related_name="marks",
        verbose_name="Project Assignment",
    )
    teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="graded_marks", verbose_name="Teacher"
    )
    score = models.DecimalField(
        max_digits=6, decimal_places=2, validators=[MinValueValidator(Decimal("0.00"))], verbose_name="Score"
    )
    max_score = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=Decimal("100.00"),
        validators=[MinValueValidator(Decimal("1.00"))],
        verbose_name="Max Score",
    )
    graded_on = models.DateTimeField(auto_now_add=True, verbose_name="Graded On")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Updated At")

    class Meta:
        ordering = ["-graded_on"]
        verbose_name = "Marks"
        verbose_name_plural = "Marks"

    def clean(self):
        super().clean()
        if self.score is not None:
            if self.score < Decimal("0.00"):
                raise ValidationError({"score": "Score cannot be negative."})
            if self.max_score is not None and self.score > self.max_score:
                raise ValidationError({"score": "Score cannot exceed maximum score."})

    @property
    def percentage(self) -> float:
        if self.max_score and self.max_score > 0:
            return round((float(self.score) / float(self.max_score)) * 100.0, 2)
        return 0.0

    @property
    def is_pass(self) -> bool:
        passing_pct = getattr(settings, "PMS_PASSING_PERCENTAGE", 40.0)
        return self.percentage >= passing_pct

    @property
    def grade_band(self) -> str:
        return get_grade_band(self.percentage)

    def __str__(self):
        return f"Marks for {self.assignment.student.get_display_name()}: {self.score}/{self.max_score} ({self.percentage}%)"
