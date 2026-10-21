from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse

from accounts.models import User, UserRole
from accounts.services import register_user


class RegistrationTests(TestCase):
    def test_student_registration_succeeds(self):
        """Student registration succeeds with valid data and required roll_no."""
        user = register_user(
            name="Alice Student",
            email="alice@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            department="Computer Science",
            roll_no="CS2024-001",
        )
        self.assertIsNotNone(user.pk)
        self.assertEqual(user.email, "alice@example.edu")
        self.assertEqual(user.role, UserRole.STUDENT)
        self.assertEqual(user.roll_no, "CS2024-001")
        self.assertIsNone(user.employee_id)
        self.assertTrue(user.is_student)
        self.assertFalse(user.is_teacher)

    def test_teacher_registration_succeeds(self):
        """Teacher registration succeeds with valid data and required employee_id."""
        user = register_user(
            name="Dr. Bob Teacher",
            email="bob@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            department="Computer Science",
            employee_id="EMP-1001",
        )
        self.assertIsNotNone(user.pk)
        self.assertEqual(user.email, "bob@example.edu")
        self.assertEqual(user.role, UserRole.TEACHER)
        self.assertEqual(user.employee_id, "EMP-1001")
        self.assertIsNone(user.roll_no)
        self.assertTrue(user.is_teacher)
        self.assertFalse(user.is_student)

    def test_duplicate_email_rejected(self):
        """Duplicate email registration is rejected."""
        register_user(
            name="User One",
            email="duplicate@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="R-01",
        )
        with self.assertRaises(ValidationError) as ctx:
            register_user(
                name="User Two",
                email="duplicate@example.edu",
                password="StrongPassword#2024",
                role=UserRole.STUDENT,
                roll_no="R-02",
            )
        self.assertIn("email", ctx.exception.message_dict)

    def test_weak_password_rejected(self):
        """Weak password rejected by Django validators."""
        with self.assertRaises(ValidationError) as ctx:
            register_user(
                name="Charlie",
                email="charlie@example.edu",
                password="123",  # Too short, entirely numeric
                role=UserRole.STUDENT,
                roll_no="CS-123",
            )
        self.assertIn("password", ctx.exception.message_dict)

    def test_student_without_roll_no_rejected(self):
        """Student registration without roll_no is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            register_user(
                name="No Roll",
                email="noroll@example.edu",
                password="StrongPassword#2024",
                role=UserRole.STUDENT,
                roll_no="",
            )
        self.assertIn("roll_no", ctx.exception.message_dict)

    def test_teacher_without_employee_id_rejected(self):
        """Teacher registration without employee_id is rejected."""
        with self.assertRaises(ValidationError) as ctx:
            register_user(
                name="No Emp",
                email="noemp@example.edu",
                password="StrongPassword#2024",
                role=UserRole.TEACHER,
                employee_id="",
            )
        self.assertIn("employee_id", ctx.exception.message_dict)

    def test_stored_password_is_hashed(self):
        """Stored password must be hashed (salted PBKDF2), never equal to plain text."""
        raw_password = "MySecurePassword#99"
        user = register_user(
            name="Hashed User", email="hashed@example.edu", password=raw_password, role=UserRole.STUDENT, roll_no="H-01"
        )
        # Verify stored password starts with a hashing algorithm prefix and is not raw text
        self.assertNotEqual(user.password, raw_password)
        self.assertTrue(user.password.startswith("pbkdf2_") or user.password.startswith("bcrypt"))
        self.assertTrue(user.check_password(raw_password))

    def test_registration_view_post_success(self):
        """Registration view accepts valid POST and redirects to login."""
        response = self.client.post(
            reverse("accounts:register"),
            {
                "name": "Web Student",
                "email": "webstudent@example.edu",
                "role": UserRole.STUDENT,
                "department": "Electronics",
                "roll_no": "ECE-2024-01",
                "password": "StrongPassword#2024",
                "password_confirm": "StrongPassword#2024",
            },
        )
        self.assertRedirects(response, reverse("accounts:login"))
        self.assertTrue(User.objects.filter(email="webstudent@example.edu").exists())
