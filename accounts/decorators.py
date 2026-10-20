from functools import wraps
from django.core.exceptions import PermissionDenied
from django.contrib.auth.views import redirect_to_login
from .models import UserRole


def teacher_required(view_func):
    """
    Decorator requiring the user to be authenticated and have the 'teacher' role.
    Anonymous users are redirected to the login page.
    Non-teacher users receive an HTTP 403 Forbidden.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_teacher:
            raise PermissionDenied("Access denied. Teacher role required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view


def student_required(view_func):
    """
    Decorator requiring the user to be authenticated and have the 'student' role.
    Anonymous users are redirected to the login page.
    Non-student users receive an HTTP 403 Forbidden.
    """
    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        if not request.user.is_student:
            raise PermissionDenied("Access denied. Student role required.")
        return view_func(request, *args, **kwargs)
    return _wrapped_view
