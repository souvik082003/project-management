from decimal import Decimal

from django import forms

from .models import Feedback, Marks


class FeedbackForm(forms.ModelForm):
    comments = forms.CharField(
        widget=forms.Textarea(
            attrs={
                "class": "form-control",
                "rows": 4,
                "placeholder": "Provide constructive feedback, noting strengths, deficiencies, and specific revision directions...",
            }
        ),
        help_text="Detailed feedback visible to the student.",
        required=True,
    )
    requested_revision = forms.BooleanField(
        required=False,
        label="Request Revision",
        widget=forms.CheckboxInput(attrs={"class": "form-check-input"}),
        help_text="If checked, assignment status moves from 'Under review' to 'Revision requested', prompting student to submit an updated deliverable.",
    )

    class Meta:
        model = Feedback
        fields = ["comments", "requested_revision"]


class MarksForm(forms.ModelForm):
    score = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("0.00"),
        label="Marks / Score",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. 85.00", "step": "0.5"}),
        help_text="Student's achieved score.",
        required=True,
    )
    max_score = forms.DecimalField(
        max_digits=6,
        decimal_places=2,
        min_value=Decimal("1.00"),
        initial=Decimal("100.00"),
        label="Maximum Score",
        widget=forms.NumberInput(attrs={"class": "form-control", "placeholder": "e.g. 100.00", "step": "1"}),
        help_text="Total maximum score available (default 100).",
        required=True,
    )

    class Meta:
        model = Marks
        fields = ["score", "max_score"]

    def clean(self):
        cleaned_data = super().clean()
        score = cleaned_data.get("score")
        max_score = cleaned_data.get("max_score")

        if score is not None and max_score is not None:
            if score < Decimal("0.00"):
                self.add_error("score", "Score cannot be negative.")
            if max_score <= Decimal("0.00"):
                self.add_error("max_score", "Max score must be greater than zero.")
            if score > max_score:
                self.add_error("score", "Score cannot exceed the maximum score.")

        return cleaned_data
