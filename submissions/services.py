"""
Business logic service layer for submissions module.
Enforces file validation, content inspection, disk storage isolation, versioning,
transactional cleanup, and permission-checked downloads.
"""

import logging
import os
import re
import uuid

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import models, transaction
from django.http import Http404

from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment

from .models import Submission

logger = logging.getLogger("pms")

# Statuses where students can submit files
ALLOWED_SUBMISSION_STATUSES = {
    AssignmentStatus.ASSIGNED,
    AssignmentStatus.IN_PROGRESS,
    AssignmentStatus.OVERDUE,
    AssignmentStatus.REVISION_REQUESTED,
}

DISALLOWED_SUBMISSION_STATUSES = {
    AssignmentStatus.SUBMITTED,
    AssignmentStatus.UNDER_REVIEW,
    AssignmentStatus.EVALUATED,
}


def sanitise_filename(raw_filename: str) -> str:
    """
    Sanitises raw upload filename to prevent path traversal and shell injection.
    Strips directory separators and non-standard characters.
    """
    if not raw_filename:
        return "unnamed_file"

    # Extract base filename and remove directory markers
    base = os.path.basename(raw_filename.replace("\\", "/"))
    # Remove leading dots to prevent hidden files
    base = base.lstrip(".")
    # Keep only safe alphanumeric, dash, dot, and underscore
    clean = re.sub(r"[^a-zA-Z0-9_.-]", "_", base)
    return clean or "submission_file"


def validate_uploaded_file(uploaded_file) -> None:
    """
    Validates file emptiness, file size against MAX_UPLOAD_SIZE,
    extension against ALLOWED_UPLOAD_EXTENSIONS, and checks magic bytes/signatures.
    Rejects disguised executables (e.g. .exe renamed to .pdf).
    """
    # 1. Empty file check
    if not uploaded_file or uploaded_file.size == 0:
        raise ValidationError({"file": "Uploaded file is empty."})

    # 2. Size limit check
    max_size = getattr(settings, "MAX_UPLOAD_SIZE", 10 * 1024 * 1024)
    if uploaded_file.size > max_size:
        max_mb = max_size // (1024 * 1024)
        raise ValidationError({"file": f"File size exceeds maximum permitted limit ({max_mb} MB)."})

    # 3. Extension check
    allowed_exts = [
        e.lower().lstrip(".")
        for e in getattr(
            settings, "ALLOWED_UPLOAD_EXTENSIONS", ["pdf", "doc", "docx", "zip", "ppt", "pptx", "txt", "png", "jpg"]
        )
    ]

    ext = os.path.splitext(uploaded_file.name)[1].lower().lstrip(".")
    if not ext or ext not in allowed_exts:
        raise ValidationError(
            {"file": f"File extension '.{ext}' is not allowed. Allowed types: {', '.join(allowed_exts)}."}
        )

    # 4. Content inspection (file signatures & magic bytes)
    header = uploaded_file.read(512)
    uploaded_file.seek(0)  # Rewind pointer for subsequent read/write

    # Prohibit executables regardless of extension (Windows PE, Linux ELF, Mach-O)
    if header.startswith(b"MZ"):
        raise ValidationError({"file": "Executable PE binary files (.exe / .dll) are strictly prohibited."})
    if header.startswith(b"\x7fELF"):
        raise ValidationError({"file": "Executable ELF binary files are strictly prohibited."})
    if (
        header.startswith(b"\xfe\xed\xfa\xce")
        or header.startswith(b"\xfe\xed\xfa\xcf")
        or header.startswith(b"\xcf\xfa\xed\xfe")
    ):
        raise ValidationError({"file": "Mach-O binary files are strictly prohibited."})

    # Format-specific signature verification
    if ext == "pdf":
        if not header.startswith(b"%PDF-"):
            raise ValidationError(
                {"file": "File signature does not match PDF format. File content is invalid or corrupted."}
            )
    elif ext == "png":
        if not header.startswith(b"\x89PNG\r\n\x1a\n"):
            raise ValidationError({"file": "File signature does not match PNG image format."})
    elif ext in ["jpg", "jpeg"]:
        if not header.startswith(b"\xff\xd8\xff"):
            raise ValidationError({"file": "File signature does not match JPEG image format."})
    elif ext in ["zip", "docx", "pptx"]:
        if not header.startswith(b"PK\x03\x04"):
            raise ValidationError({"file": f"File signature does not match {ext.upper()} archive/document format."})


def notify_teacher_new_submission(submission: Submission) -> None:
    """
    Notifies supervising teacher of student deliverable upload.
    Real email delivery and in-app alert dispatched non-blockingly.
    """
    try:
        from dashboard import notifications as dashboard_notifications

        dashboard_notifications.notify_teacher_new_submission(submission)
    except Exception as err:
        logger.warning(f"Submission notification failed (non-blocking): {err}")


def submit_file(assignment: ProjectAssignment, uploaded_file, user) -> Submission:
    """
    Handles file upload, verification, disk storage, versioning, atomic state transitions,
    and orphan cleanup on failure.
    Design Decision: If assignment is in 'Assigned' status, it automatically transitions
    Assigned -> In progress -> Submitted, providing a smooth student workflow.
    """
    if assignment.student_id != user.id:
        raise Http404("Assignment not found.")

    if assignment.status in DISALLOWED_SUBMISSION_STATUSES:
        raise ValidationError(f"Submissions are not permitted while project is '{assignment.get_status_display()}'.")

    # Validate file
    validate_uploaded_file(uploaded_file)

    safe_name = sanitise_filename(uploaded_file.name)
    max_version = assignment.submissions.aggregate(models.Max("version"))["version__max"] or 0
    version = max_version + 1

    file_uuid = uuid.uuid4().hex
    relative_path = f"uploads/{assignment.id}/{file_uuid}_{safe_name}"
    full_dest_path = os.path.join(settings.MEDIA_ROOT, relative_path)

    saved_disk_path = None
    try:
        # 1. Save file to disk
        os.makedirs(os.path.dirname(full_dest_path), exist_ok=True)
        with open(full_dest_path, "wb+") as destination:
            destination.writelines(uploaded_file.chunks())
        saved_disk_path = full_dest_path

        # 2. Database transaction: create Submission and transition state machine
        with transaction.atomic():
            submission = Submission.objects.create(
                assignment=assignment,
                file_path=relative_path,
                file_name=safe_name,
                file_size=uploaded_file.size,
                version=version,
            )

            # State machine transitions
            if (
                assignment.status == AssignmentStatus.ASSIGNED
                or assignment.status == AssignmentStatus.REVISION_REQUESTED
            ):
                assignment_services.transition(assignment, AssignmentStatus.IN_PROGRESS)
                assignment_services.transition(assignment, AssignmentStatus.SUBMITTED)
            elif assignment.status in [AssignmentStatus.IN_PROGRESS, AssignmentStatus.OVERDUE]:
                assignment_services.transition(assignment, AssignmentStatus.SUBMITTED)

        # 3. Notification (failures must never break submission)
        try:
            notify_teacher_new_submission(submission)
        except Exception as notify_err:
            logger.warning(f"Submission notification failed (non-blocking): {notify_err}")

        logger.info(f"Submission v{version} created for Assignment {assignment.id}: {safe_name}")
        return submission

    except Exception:
        # Atomic cleanup: if DB creation or transitions fail, remove orphaned disk file
        if saved_disk_path and os.path.exists(saved_disk_path):
            try:
                os.remove(saved_disk_path)
            except OSError as cleanup_err:
                logger.error(f"Failed to clean up orphaned file {saved_disk_path}: {cleanup_err}")
        raise


def teacher_open_submission(submission, teacher) -> Submission:
    """
    Teacher opens/views a submission.
    Transitions assignment Submitted -> Under review on the first inspection.
    """
    if isinstance(submission, int):
        try:
            submission = Submission.objects.select_related("assignment", "assignment__project").get(pk=submission)
        except Submission.DoesNotExist:
            raise Http404("Submission not found.")

    if submission.assignment.project.created_by_id != teacher.id:
        raise Http404("Submission not found.")

    assignment = submission.assignment
    if assignment.status == AssignmentStatus.SUBMITTED:
        assignment_services.transition(assignment, AssignmentStatus.UNDER_REVIEW)

    return submission


def get_submission_for_download(submission_id: int, user) -> tuple[Submission, str]:
    """
    Verifies download permissions and returns submission instance and absolute file path.
    Students can only download their own submissions; teachers only their own projects' files.
    """
    try:
        submission = Submission.objects.select_related("assignment", "assignment__project", "assignment__student").get(
            pk=submission_id
        )
    except Submission.DoesNotExist:
        raise Http404("Submission not found.")

    # Role permission check
    if getattr(user, "is_student", False):
        if submission.assignment.student_id != user.id:
            raise PermissionDenied("You are not permitted to download this submission.")
    elif getattr(user, "is_teacher", False):
        if submission.assignment.project.created_by_id != user.id:
            raise Http404("Submission not found.")
        # If teacher downloads, trigger Submitted -> Under review
        if submission.assignment.status == AssignmentStatus.SUBMITTED:
            assignment_services.transition(submission.assignment, AssignmentStatus.UNDER_REVIEW)
    else:
        raise PermissionDenied("Access denied.")

    full_path = os.path.join(settings.MEDIA_ROOT, submission.file_path)
    if not os.path.exists(full_path):
        raise Http404("Submission file was not found on the server.")

    return submission, full_path
