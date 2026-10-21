from django import forms

from .models import ProgressUpdate


class ProgressUpdateForm(forms.ModelForm):
    class Meta:
        model = ProgressUpdate
        fields = ["percent_complete", "remarks"]
        widgets = {
            "percent_complete": forms.NumberInput(
                attrs={"class": "form-control", "min": "0", "max": "100", "placeholder": "Enter 0 - 100"}
            ),
            "remarks": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Summarize your recent progress, completed tasks, and next steps...",
                }
            ),
        }
