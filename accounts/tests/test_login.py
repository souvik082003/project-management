from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserRole
from accounts.services import authenticate_user, register_user


class LoginAndLockoutTests(TestCase):
    def setUp(self):
        self.password = "StrongPassword#2024"
        self.student = register_user(
            name="Alice Student",
            email="alice@example.edu",
            password=self.password,
            role=UserRole.STUDENT,
            roll_no="S-001",
        )
        self.teacher = register_user(
            name="Dr. Bob Teacher",
            email="bob@example.edu",
            password=self.password,
            role=UserRole.TEACHER,
            employee_id="T-001",
        )

    def test_successful_login_redirects_to_dashboard(self):
        """Successful login redirects user to dashboard."""
        response = self.client.post(
            reverse("accounts:login"), {"email": "alice@example.edu", "password": self.password}
        )
        self.assertRedirects(response, "/dashboard/")
        self.assertEqual(int(self.client.session["_auth_user_id"]), self.student.pk)

    def test_wrong_password_shows_generic_error(self):
        """Wrong password shows a generic error and does not log in."""
        response = self.client.post(
            reverse("accounts:login"), {"email": "alice@example.edu", "password": "WrongPassword123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")
        self.student.refresh_from_db()
        self.assertEqual(self.student.failed_login_attempts, 1)

    def test_nonexistent_email_shows_same_generic_error(self):
        """Nonexistent email shows identical error message without revealing existence."""
        response = self.client.post(
            reverse("accounts:login"), {"email": "nonexistent@example.edu", "password": "SomePassword123"}
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Invalid email or password.")

    def test_lockout_after_5_failures_and_unlock_after_15_minutes(self):
        """
        After 5 consecutive failed attempts, user is locked for 15 minutes.
        After 15 minutes have passed (mocked time), login succeeds.
        """
        now = timezone.now()

        # 4 failed attempts: user is not locked yet
        for i in range(1, 5):
            with self.assertRaises(ValidationError) as ctx:
                authenticate_user(None, "alice@example.edu", "WrongPass", now=now)
            self.assertIn("Invalid email or password", str(ctx.exception))
            self.student.refresh_from_db()
            self.assertEqual(self.student.failed_login_attempts, i)
            self.assertFalse(self.student.is_locked(now=now))

        # 5th failed attempt: user gets locked out for 15 minutes
        with self.assertRaises(ValidationError) as ctx:
            authenticate_user(None, "alice@example.edu", "WrongPass", now=now)
        self.assertIn("Account is temporarily locked", str(ctx.exception))

        self.student.refresh_from_db()
        self.assertEqual(self.student.failed_login_attempts, 5)
        self.assertTrue(self.student.is_locked(now=now))

        # Even with the CORRECT password, login is blocked while locked out (e.g. at 10 minutes)
        ten_minutes_later = now + timedelta(minutes=10)
        with self.assertRaises(ValidationError) as ctx:
            authenticate_user(None, "alice@example.edu", self.password, now=ten_minutes_later)
        self.assertIn("Account is temporarily locked", str(ctx.exception))

        # After 15 minutes (at 15 minutes + 1 second), account unlocks with correct password
        sixteen_minutes_later = now + timedelta(minutes=15, seconds=1)
        self.assertFalse(self.student.is_locked(now=sixteen_minutes_later))
        authenticated_user = authenticate_user(None, "alice@example.edu", self.password, now=sixteen_minutes_later)
        self.assertEqual(authenticated_user.pk, self.student.pk)

        # Upon successful authentication, failed attempts counter is reset
        self.student.refresh_from_db()
        self.assertEqual(self.student.failed_login_attempts, 0)
        self.assertIsNone(self.student.locked_until)

    def test_successful_login_resets_prior_failed_attempts(self):
        """A successful login resets consecutive failed attempts counter."""
        now = timezone.now()
        # 3 failed attempts
        for _ in range(3):
            try:
                authenticate_user(None, "alice@example.edu", "WrongPass", now=now)
            except ValidationError:
                pass
        self.student.refresh_from_db()
        self.assertEqual(self.student.failed_login_attempts, 3)

        # Correct login resets counter
        user = authenticate_user(None, "alice@example.edu", self.password, now=now)
        self.assertEqual(user.failed_login_attempts, 0)
        self.student.refresh_from_db()
        self.assertEqual(self.student.failed_login_attempts, 0)
