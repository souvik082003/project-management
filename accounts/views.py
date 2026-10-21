from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from . import services
from .forms import ChangePasswordForm, LoginForm, UserProfileForm, UserRegistrationForm


def register_view(request):
    """
    User registration controller for students and teachers.
    Parses request, calls services.register_user, and renders response.
    """
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    if request.method == "POST":
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            try:
                services.register_user(
                    name=form.cleaned_data["name"],
                    email=form.cleaned_data["email"],
                    password=form.cleaned_data["password"],
                    role=form.cleaned_data["role"],
                    department=form.cleaned_data.get("department", ""),
                    roll_no=form.cleaned_data.get("roll_no"),
                    employee_id=form.cleaned_data.get("employee_id"),
                )
                messages.success(request, "Registration successful! You may now log in.")
                return redirect("accounts:login")
            except ValidationError as err:
                if hasattr(err, "message_dict"):
                    for field, err_list in err.message_dict.items():
                        for message in err_list:
                            form.add_error(field if field in form.fields else None, message)
                else:
                    for message in err.messages:
                        form.add_error(None, message)
    else:
        form = UserRegistrationForm()

    return render(request, "accounts/register.html", {"form": form})


def login_view(request):
    """
    User login controller with brute-force protection.
    Calls services.authenticate_user and logs in valid users.
    """
    if request.user.is_authenticated:
        return redirect("/dashboard/")

    next_url = request.GET.get("next") or request.POST.get("next", "")

    if request.method == "POST":
        form = LoginForm(request.POST)
        if form.is_valid():
            try:
                user = services.authenticate_user(
                    request=request, email=form.cleaned_data["email"], password=form.cleaned_data["password"]
                )
                auth_login(request, user)
                messages.success(request, f"Welcome, {user.get_display_name()}!")
                if next_url:
                    return redirect(next_url)
                return redirect("/dashboard/")
            except ValidationError as err:
                error_msg = err.messages[0] if hasattr(err, "messages") else str(err)
                messages.error(request, error_msg)
    else:
        form = LoginForm()

    return render(request, "accounts/login.html", {"form": form, "next": next_url})


def logout_view(request):
    """
    Logout controller enforcing POST method.
    """
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"], "Method Not Allowed: Logout requires a POST request.")

    auth_logout(request)
    messages.info(request, "You have been successfully logged out.")
    return redirect("accounts:login")


@login_required
def profile_view(request):
    """
    View and update user profile information.
    """
    if request.method == "POST":
        form = UserProfileForm(request.POST)
        if form.is_valid():
            try:
                services.update_user_profile(
                    user=request.user, name=form.cleaned_data["name"], department=form.cleaned_data["department"]
                )
                messages.success(request, "Profile updated successfully.")
                return redirect("accounts:profile")
            except ValidationError as err:
                for message in err.messages:
                    form.add_error(None, message)
    else:
        form = UserProfileForm(
            initial={
                "name": request.user.name,
                "department": request.user.department,
            }
        )

    return render(request, "accounts/profile.html", {"form": form, "user_obj": request.user})


@login_required
def change_password_view(request):
    """
    Change password controller.
    """
    if request.method == "POST":
        form = ChangePasswordForm(request.POST)
        if form.is_valid():
            try:
                services.change_user_password(
                    user=request.user,
                    old_password=form.cleaned_data["old_password"],
                    new_password=form.cleaned_data["new_password"],
                )
                update_session_auth_hash(request, request.user)
                messages.success(request, "Your password has been changed successfully.")
                return redirect("accounts:profile")
            except ValidationError as err:
                if hasattr(err, "message_dict"):
                    for field, err_list in err.message_dict.items():
                        for message in err_list:
                            form.add_error(field if field in form.fields else None, message)
                else:
                    for message in err.messages:
                        form.add_error(None, message)
    else:
        form = ChangePasswordForm()

    return render(request, "accounts/change_password.html", {"form": form})
