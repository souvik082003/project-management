from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from . import services


def home_view(request):
    """
    Public landing page for PMS. If authenticated, redirects to dashboard.
    """
    if request.user.is_authenticated:
        return redirect("dashboard:dashboard")
    return render(request, "dashboard/home.html")


@login_required
def dashboard_view(request):
    """
    UC17 Role-specific PMS dashboard.
    Renders personalized student dashboard or teacher supervisory dashboard.
    """
    if getattr(request.user, "is_teacher", False):
        data = services.get_teacher_dashboard_data(request.user)
        return render(request, "dashboard/teacher_dashboard.html", data)
    elif getattr(request.user, "is_student", False):
        data = services.get_student_dashboard_data(request.user)
        return render(request, "dashboard/student_dashboard.html", data)
    else:
        # Fallback for admin or unassigned roles
        return render(request, "dashboard/dashboard.html", {"user": request.user})


@login_required
def notifications_list_view(request):
    """
    Lists in-app notifications for authenticated user.
    """
    notifications = services.get_user_notifications(request.user)
    return render(request, "dashboard/notifications_list.html", {"notifications": notifications})


@login_required
def mark_notification_read_view(request, notification_id: int):
    """
    Marks a single notification as read and navigates to target link if present.
    """
    notification = services.mark_notification_as_read(request.user, notification_id)
    if notification.link:
        return redirect(notification.link)
    return redirect("dashboard:notifications_list")


@login_required
@require_POST
def mark_all_notifications_read_view(request):
    """
    Marks all notifications for current user as read.
    """
    count = services.mark_all_notifications_as_read(request.user)
    messages.success(request, f"Marked {count} notification(s) as read.")
    return redirect("dashboard:notifications_list")
