from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone
from datetime import timedelta


class UserRole(models.TextChoices):
    STUDENT = 'student', 'Student'
    TEACHER = 'teacher', 'Teacher'


class User(AbstractUser):
    # Enforce unique email and use as username identifier
    email = models.EmailField(unique=True, verbose_name="Email Address")
    name = models.CharField(max_length=150, verbose_name="Full Name")
    role = models.CharField(
        max_length=20,
        choices=UserRole.choices,
        default=UserRole.STUDENT,
        verbose_name="User Role"
    )
    department = models.CharField(max_length=100, blank=True, verbose_name="Department")
    roll_no = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Roll Number"
    )
    employee_id = models.CharField(
        max_length=50,
        blank=True,
        null=True,
        verbose_name="Employee ID"
    )

    # Brute-force protection fields
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'name', 'role']

    def save(self, *args, **kwargs):
        # Guarantee username mirrors email if not explicitly set
        if not self.username:
            self.username = self.email
        super().save(*args, **kwargs)

    @property
    def is_teacher(self):
        return self.role == UserRole.TEACHER

    @property
    def is_student(self):
        return self.role == UserRole.STUDENT

    def is_locked(self, now=None):
        """Check if account is currently locked out."""
        current_time = now or timezone.now()
        if self.locked_until and self.locked_until > current_time:
            return True
        return False

    def record_failed_attempt(self, now=None):
        """Record a failed login attempt and lock for 15 minutes upon 5 failures."""
        current_time = now or timezone.now()
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= 5:
            self.locked_until = current_time + timedelta(minutes=15)
        self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def reset_failed_attempts(self):
        """Reset failed attempts and unlock account upon successful login."""
        if self.failed_login_attempts > 0 or self.locked_until is not None:
            self.failed_login_attempts = 0
            self.locked_until = None
            self.save(update_fields=['failed_login_attempts', 'locked_until'])

    def get_display_name(self):
        return self.name or self.get_full_name() or self.email

    def __str__(self):
        return f"{self.email} ({self.get_role_display()})"
