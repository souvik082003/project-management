from django.test import TestCase
from django.urls import reverse

from accounts.models import UserRole
from accounts.services import register_user


class AuthFlowAndProfileTests(TestCase):
    def setUp(self):
        self.password = "StrongPassword#2024"
        self.student = register_user(
            name="Alice Student",
            email="alice@example.edu",
            password=self.password,
            role=UserRole.STUDENT,
            department="Computer Science",
            roll_no="CS-001",
        )
        self.teacher = register_user(
            name="Dr. Bob Teacher",
            email="bob@example.edu",
            password=self.password,
            role=UserRole.TEACHER,
            department="Electrical",
            employee_id="EE-101",
        )

    def test_logout_requires_post(self):
        """GET request to logout view returns 405 Method Not Allowed."""
        self.client.force_login(self.student)
        get_response = self.client.get(reverse("accounts:logout"))
        self.assertEqual(get_response.status_code, 405)

        # POST request logs the user out
        post_response = self.client.post(reverse("accounts:logout"))
        self.assertRedirects(post_response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_profile_view_and_update(self):
        """Authenticated user can view and update their profile."""
        self.client.force_login(self.student)
        response = self.client.get(reverse("accounts:profile"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Alice Student")
        self.assertContains(response, "CS-001")

        # Update name and department
        post_response = self.client.post(
            reverse("accounts:profile"), {"name": "Alice Updated", "department": "Data Science"}
        )
        self.assertRedirects(post_response, reverse("accounts:profile"))
        self.student.refresh_from_db()
        self.assertEqual(self.student.name, "Alice Updated")
        self.assertEqual(self.student.department, "Data Science")

    def test_change_password_view(self):
        """User can change their password successfully."""
        self.client.force_login(self.student)
        new_pass = "NewStrongPassword#2025"
        response = self.client.post(
            reverse("accounts:change_password"),
            {"old_password": self.password, "new_password": new_pass, "confirm_password": new_pass},
        )
        self.assertRedirects(response, reverse("accounts:profile"))
        self.student.refresh_from_db()
        self.assertTrue(self.student.check_password(new_pass))

    def test_dashboard_shows_welcome_and_role(self):
        """Dashboard renders welcome message and role info."""
        self.client.force_login(self.student)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, Alice Student")
        self.assertContains(response, "Student")

        self.client.force_login(self.teacher)
        response = self.client.get("/dashboard/")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Welcome, Dr. Bob Teacher")
        self.assertContains(response, "Teacher")
