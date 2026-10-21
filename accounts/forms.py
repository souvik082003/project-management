from django import forms

from .models import UserRole


class UserRegistrationForm(forms.Form):
    name = forms.CharField(
        max_length=150,
        required=True,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. John Doe"}),
    )
    email = forms.EmailField(
        required=True, widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.edu"})
    )
    role = forms.ChoiceField(
        choices=UserRole.choices,
        initial=UserRole.STUDENT,
        widget=forms.Select(attrs={"class": "form-select", "id": "id_role"}),
    )
    department = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. Computer Science"}),
    )
    roll_no = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. CS2024-042"}),
    )
    employee_id = forms.CharField(
        max_length=50,
        required=False,
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "e.g. EMP-9921"}),
    )
    password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Enter strong password"}),
    )
    password_confirm = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm your password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")
        role = cleaned_data.get("role")
        roll_no = cleaned_data.get("roll_no")
        employee_id = cleaned_data.get("employee_id")

        if password and password_confirm and password != password_confirm:
            self.add_error("password_confirm", "Passwords do not match.")

        if role == UserRole.STUDENT and not roll_no:
            self.add_error("roll_no", "Roll number is required for students.")
        elif role == UserRole.TEACHER and not employee_id:
            self.add_error("employee_id", "Employee ID is required for teachers.")

        return cleaned_data


class LoginForm(forms.Form):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={"class": "form-control", "placeholder": "name@example.edu", "autofocus": True}),
    )
    password = forms.CharField(
        required=True, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Enter password"})
    )


class UserProfileForm(forms.Form):
    name = forms.CharField(max_length=150, required=True, widget=forms.TextInput(attrs={"class": "form-control"}))
    department = forms.CharField(
        max_length=100, required=False, widget=forms.TextInput(attrs={"class": "form-control"})
    )


class ChangePasswordForm(forms.Form):
    old_password = forms.CharField(
        required=True, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Current password"})
    )
    new_password = forms.CharField(
        required=True, widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "New password"})
    )
    confirm_password = forms.CharField(
        required=True,
        widget=forms.PasswordInput(attrs={"class": "form-control", "placeholder": "Confirm new password"}),
    )

    def clean(self):
        cleaned_data = super().clean()
        new_password = cleaned_data.get("new_password")
        confirm_password = cleaned_data.get("confirm_password")

        if new_password and confirm_password and new_password != confirm_password:
            self.add_error("confirm_password", "New passwords do not match.")

        return cleaned_data
