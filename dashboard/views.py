from django.shortcuts import render
from django.contrib.auth.decorators import login_required


def home_view(request):
    """
    Landing/home page for PMS.
    """
    return render(request, 'dashboard/home.html')


@login_required
def dashboard_view(request):
    """
    Role-specific dashboard placeholder (full implementation in Sprint 6).
    Displays welcome message, role badge, and basic academic profile info.
    """
    return render(request, 'dashboard/dashboard.html', {'user': request.user})
