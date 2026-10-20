"""
Business logic service layer for accounts module.
Contains all business rules for user registration, authentication, lockout protection,
profile management, and password updates.
"""
from django.core.exceptions import ValidationError
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from .models import User, UserRole


def register_user(
    name: str,
    email: str,
    password: str,
    role: str,
    department: str = "",
    roll_no: str | None = None,
    employee_id: str | None = None
) -> User:
    """
    Registers a new student or teacher user with validation.
    Enforces email uniqueness, password strength, and role-specific requirements.
    """
    email = (email or "").strip().lower()
    name = (name or "").strip()
    department = (department or "").strip()
    roll_no = (roll_no or "").strip() if roll_no else ""
    employee_id = (employee_id or "").strip() if employee_id else ""

    if not name:
        raise ValidationError({"name": "Full name is required."})

    if not email:
        raise ValidationError({"email": "Email address is required."})

    if User.objects.filter(email__iexact=email).exists():
        raise ValidationError({"email": "A user with this email already exists."})

    if role not in [UserRole.STUDENT, UserRole.TEACHER]:
        raise ValidationError({"role": f"Invalid role selected: {role}."})

    # Validate role-specific fields
    if role == UserRole.STUDENT:
        if not roll_no:
            raise ValidationError({"roll_no": "Roll number is required for students."})
        employee_id = None
    elif role == UserRole.TEACHER:
        if not employee_id:
            raise ValidationError({"employee_id": "Employee ID is required for teachers."})
        roll_no = None

    # Validate password using Django's password validators
    temp_user = User(email=email, username=email, name=name, role=role)
    try:
        validate_password(password, user=temp_user)
    except ValidationError as err:
        raise ValidationError({"password": list(err.messages)})

    # Create and return user with properly hashed password
    user = User.objects.create_user(
        username=email,
        email=email,
        password=password,
        name=name,
        role=role,
        department=department,
        roll_no=roll_no,
        employee_id=employee_id
    )
    return user


def authenticate_user(
    request,
    email: str,
    password: str,
    now=None
) -> User:
    """
    Authenticates a user via email and password with brute-force lockout protection.
    Locks the account for 15 minutes after 5 consecutive failures.
    Returns generic error messages to prevent user enumeration.
    """
    email = (email or "").strip().lower()
    password = password or ""
    current_time = now or timezone.now()

    if not email or not password:
        raise ValidationError("Invalid email or password.")

    user = User.objects.filter(email__iexact=email).first()

    if user:
        if user.is_locked(now=current_time):
            raise ValidationError("Account is temporarily locked due to too many failed attempts. Please try again later.")

        if user.check_password(password):
            if not user.is_active:
                raise ValidationError("This account is inactive.")
            user.reset_failed_attempts()
            return user
        else:
            user.record_failed_attempt(now=current_time)
            if user.is_locked(now=current_time):
                raise ValidationError("Account is temporarily locked due to too many failed attempts. Please try again later.")
            raise ValidationError("Invalid email or password.")
    else:
        # Nonexistent user: generic error message
        raise ValidationError("Invalid email or password.")


def update_user_profile(user: User, name: str, department: str) -> User:
    """
    Updates basic profile fields for the authenticated user.
    """
    name = (name or "").strip()
    department = (department or "").strip()

    if not name:
        raise ValidationError({"name": "Full name cannot be empty."})

    user.name = name
    user.department = department
    user.save(update_fields=['name', 'department'])
    return user


def change_user_password(user: User, old_password: str, new_password: str) -> None:
    """
    Validates old password and sets new password with password validators.
    """
    if not user.check_password(old_password):
        raise ValidationError({"old_password": "The current password entered is incorrect."})

    try:
        validate_password(new_password, user=user)
    except ValidationError as err:
        raise ValidationError({"new_password": list(err.messages)})

    user.set_password(new_password)
    user.save(update_fields=['password'])
