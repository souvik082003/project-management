from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase

from accounts.decorators import student_required, teacher_required
from accounts.models import UserRole
from accounts.services import register_user


# Dummy view functions wrapped with the decorators
@teacher_required
def dummy_teacher_view(request):
    return HttpResponse("Teacher View Content", status=200)


@student_required
def dummy_student_view(request):
    return HttpResponse("Student View Content", status=200)


class RoleDecoratorsTests(TestCase):
    def setUp(self):
        self.factory = RequestFactory()
        self.student = register_user(
            name="Student Sam",
            email="sam@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="SAM-01",
        )
        self.teacher = register_user(
            name="Prof Tina",
            email="tina@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="TINA-01",
        )

    def test_anonymous_redirected_to_login_by_teacher_required(self):
        """Anonymous user trying to access teacher view is redirected to login."""
        request = self.factory.get("/some-teacher-url/")
        request.user = AnonymousUser()
        response = dummy_teacher_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_anonymous_redirected_to_login_by_student_required(self):
        """Anonymous user trying to access student view is redirected to login."""
        request = self.factory.get("/some-student-url/")
        request.user = AnonymousUser()
        response = dummy_student_view(request)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/accounts/login/", response.url)

    def test_student_opening_teacher_only_view_gets_403(self):
        """A student opening a teacher-only view raises PermissionDenied (HTTP 403)."""
        request = self.factory.get("/teacher-action/")
        request.user = self.student
        with self.assertRaises(PermissionDenied):
            dummy_teacher_view(request)

    def test_teacher_opening_student_only_view_gets_403(self):
        """A teacher opening a student-only view raises PermissionDenied (HTTP 403)."""
        request = self.factory.get("/student-action/")
        request.user = self.teacher
        with self.assertRaises(PermissionDenied):
            dummy_student_view(request)

    def test_teacher_opening_teacher_view_succeeds(self):
        """A teacher opening a teacher view receives 200 OK."""
        request = self.factory.get("/teacher-action/")
        request.user = self.teacher
        response = dummy_teacher_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Teacher View Content")

    def test_student_opening_student_view_succeeds(self):
        """A student opening a student view receives 200 OK."""
        request = self.factory.get("/student-action/")
        request.user = self.student
        response = dummy_student_view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content.decode(), "Student View Content")
