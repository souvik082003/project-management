from django import forms
from django.utils import timezone

from .models import Project


class ProjectForm(forms.ModelForm):
    deadline = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={"class": "form-control", "type": "datetime-local"}, format="%Y-%m-%dT%H:%M"),
        input_formats=["%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"],
    )

    class Meta:
        model = Project
        fields = ["title", "description", "deadline"]
        widgets = {
            "title": forms.TextInput(
                attrs={"class": "form-control", "placeholder": "e.g. Distributed Cache Implementation"}
            ),
            "description": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 5,
                    "placeholder": "Provide scope, deliverables, and assessment criteria...",
                }
            ),
        }

    def clean_deadline(self):
        deadline = self.cleaned_data.get("deadline")
        # Only enforce future deadline when creating new project
        if not self.instance.pk and deadline and deadline < timezone.now():
            raise forms.ValidationError("Deadline cannot be in the past on creation.")
        return deadline
