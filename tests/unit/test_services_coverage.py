"""
Targeted tests to achieve >=85% coverage across all services.py modules:
- accounts/services.py
- projects/services.py
- assignments/services.py
- progress/services.py
- submissions/services.py
- reviews/services.py
- dashboard/services.py
"""

import os
import shutil
import tempfile
from datetime import timedelta
from decimal import Decimal

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.test import TestCase, override_settings
from django.utils import timezone

from accounts import services as accounts_services
from accounts.models import User, UserRole
from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from dashboard import services as dashboard_services
from dashboard.models import Notification
from progress import services as progress_services
from projects import services as project_services
from projects.models import ProjectStatus
from reviews import services as reviews_services
from submissions import services as submission_services


class TestServicesCoverage(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        )
        self.settings_override.enable()
        self.now = timezone.now()

        # Users
        self.teacher = User.objects.create_user(
            username="teacher.cov@example.edu",
            email="teacher.cov@example.edu",
            password="TeacherPass@123",
            name="Teacher Cov",
            role=UserRole.TEACHER,
            department="CSE",
            employee_id="TCOV01",
        )

        self.student = User.objects.create_user(
            username="student.cov@example.edu",
            email="student.cov@example.edu",
            password="StudentPass@123",
            name="Student Cov",
            role=UserRole.STUDENT,
            department="CSE",
            roll_no="SCOV01",
        )

        self.other_teacher = User.objects.create_user(
            username="other.teacher@example.edu",
            email="other.teacher@example.edu",
            password="TeacherPass@123",
            name="Other Teacher",
            role=UserRole.TEACHER,
            department="IT",
            employee_id="TCOV02",
        )

    def tearDown(self):
        self.settings_override.disable()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    # --- accounts/services.py ---
    def test_accounts_services_edge_cases(self):
        # 1. Register with empty/invalid fields
        with self.assertRaises(ValidationError):
            accounts_services.register_user(
                email="bad.student@example.edu",
                password="ValidPass@123",
                name="Bad Student",
                role=UserRole.STUDENT,
                department="CSE",
                roll_no="",  # Missing roll_no
            )

        with self.assertRaises(ValidationError):
            accounts_services.register_user(
                email="bad.teacher@example.edu",
                password="ValidPass@123",
                name="Bad Teacher",
                role=UserRole.TEACHER,
                department="CSE",
                employee_id="",  # Missing employee_id
            )

        with self.assertRaises(ValidationError):
            accounts_services.register_user(
                email="", password="ValidPass@123", name="Bad Teacher", role=UserRole.TEACHER, employee_id="EMP99"
            )

        with self.assertRaises(ValidationError):
            accounts_services.register_user(
                email="teacher.cov@example.edu",  # Duplicate email
                password="ValidPass@123",
                name="Duplicate",
                role=UserRole.TEACHER,
                employee_id="EMP99",
            )

        with self.assertRaises(ValidationError):
            accounts_services.register_user(
                email="invalidrole@example.edu",
                password="ValidPass@123",
                name="Invalid Role",
                role="admin_unsupported",
            )

        # 2. Update profile with non-existent user or invalid values
        with self.assertRaises(ValidationError):
            accounts_services.update_user_profile(user=self.student, name="", department="CSE")

        updated_student = accounts_services.update_user_profile(
            user=self.student, name="Student Cov Updated", department="ECE"
        )
        self.assertEqual(updated_student.name, "Student Cov Updated")
        self.assertEqual(updated_student.department, "ECE")

        # 3. Change password with incorrect current password
        with self.assertRaises(ValidationError):
            accounts_services.change_user_password(
                user=self.student, old_password="WrongCurrentPassword@999", new_password="NewValidPassword@123"
            )

        # Valid password change
        accounts_services.change_user_password(
            user=self.student, old_password="StudentPass@123", new_password="NewStudentPass@123"
        )
        self.assertTrue(self.student.check_password("NewStudentPass@123"))

        # Inactive user authentication
        inactive_user = User.objects.create_user(
            username="inactive@example.edu",
            email="inactive@example.edu",
            password="InactivePass@123",
            name="Inactive User",
            role=UserRole.STUDENT,
            roll_no="INACT01",
            is_active=False,
        )
        with self.assertRaises(ValidationError):
            accounts_services.authenticate_user(None, "inactive@example.edu", "InactivePass@123")

        # Authenticate empty credentials
        with self.assertRaises(ValidationError):
            accounts_services.authenticate_user(None, "", "")

        # Authenticate nonexistent user
        with self.assertRaises(ValidationError):
            accounts_services.authenticate_user(None, "nonexistent@example.edu", "SomePass@123")

    # --- projects/services.py ---
    def test_projects_services_edge_cases(self):
        # 1. Non-teacher creates project
        with self.assertRaises(ValidationError):
            project_services.create_project(
                teacher=self.student, title="Invalid Creator", description="desc", deadline=self.now + timedelta(days=5)
            )

        # 2. Empty title, description, or None/past deadline
        with self.assertRaises(ValidationError):
            project_services.create_project(self.teacher, "", "desc", self.now + timedelta(days=5))

        with self.assertRaises(ValidationError):
            project_services.create_project(self.teacher, "Title", "", self.now + timedelta(days=5))

        with self.assertRaises(ValidationError):
            project_services.create_project(self.teacher, "Title", "desc", None)

        with self.assertRaises(ValidationError):
            project_services.create_project(self.teacher, "Title", "desc", self.now - timedelta(days=1))

        # 3. Valid project
        proj = project_services.create_project(self.teacher, "Valid Title", "Valid Desc", self.now + timedelta(days=5))

        # 4. State transitions: Draft -> Assigned -> Closed; test invalid transitions
        project_services.transition(proj, ProjectStatus.ASSIGNED)
        self.assertEqual(proj.status, ProjectStatus.ASSIGNED)
        project_services.transition(proj, ProjectStatus.CLOSED)
        self.assertEqual(proj.status, ProjectStatus.CLOSED)

        with self.assertRaises(project_services.InvalidTransition):
            project_services.transition(proj, ProjectStatus.DRAFT)

        # Recreate project for update tests
        proj2 = project_services.create_project(
            self.teacher, "Valid Title 2", "Valid Desc 2", self.now + timedelta(days=5)
        )

        # 5. Update project validations
        with self.assertRaises(Http404):
            project_services.update_project(proj2, self.other_teacher, "Title", "Desc", self.now + timedelta(days=5))

        with self.assertRaises(ValidationError):
            project_services.update_project(proj2, self.teacher, "", "Desc", self.now + timedelta(days=5))

        with self.assertRaises(ValidationError):
            project_services.update_project(proj2, self.teacher, "Title", "", self.now + timedelta(days=5))

        with self.assertRaises(ValidationError):
            project_services.update_project(proj2, self.teacher, "Title", "Desc", None)

        updated_p = project_services.update_project(
            proj2, self.teacher, "Updated Title", "Updated Desc", self.now + timedelta(days=10)
        )
        self.assertEqual(updated_p.title, "Updated Title")

        # 6. Query projects
        qs = project_services.get_teacher_projects(self.teacher, status=ProjectStatus.DRAFT)
        self.assertIn(proj2, qs)
        p_fetched = project_services.get_teacher_project_or_404(proj2.id, self.teacher)
        self.assertEqual(p_fetched.id, proj2.id)

        with self.assertRaises(Http404):
            project_services.get_teacher_project_or_404(999999, self.teacher)

        # 7. Report data with progress and submissions
        assignment_services.assign_students_to_project(self.teacher, proj2, [self.student.id])
        asgn = ProjectAssignment.objects.get(project=proj2, student=self.student)
        progress_services.add_progress_update(self.student, asgn, 50, "Halfway done")

        pdf_file = SimpleUploadedFile("report.pdf", b"%PDF-1.4\ncontent\n%%EOF", content_type="application/pdf")
        submission_services.submit_file(asgn, pdf_file, self.student)

        report_rows = project_services.generate_project_report_data(proj2, self.teacher)
        self.assertEqual(len(report_rows), 1)
        self.assertEqual(report_rows[0]["latest_progress"], "50%")
        self.assertEqual(report_rows[0]["submissions_count"], "1")

        # 8. CSV report export
        csv_str = project_services.generate_project_csv_report(proj2, self.teacher)
        self.assertIn("Student Name", csv_str)
        self.assertIn(self.student.name, csv_str)

        with self.assertRaises(Http404):
            project_services.generate_project_report_data(proj2, self.other_teacher)

    # --- assignments/services.py ---
    def test_assignments_services_edge_cases(self):
        proj = project_services.create_project(
            self.teacher, "Assignment Edge Cases", "Desc", self.now + timedelta(days=1)
        )

        # 1. Unauthorized teacher assigns students
        with self.assertRaises(Http404):
            assignment_services.assign_students_to_project(self.other_teacher, proj, [self.student.id])

        # 2. Empty student list
        with self.assertRaises(ValidationError):
            assignment_services.assign_students_to_project(self.teacher, proj, [])

        # 3. Valid assignment and skip on duplicate
        assigned, skipped = assignment_services.assign_students_to_project(self.teacher, proj, [self.student.id])
        self.assertEqual(assigned, 1)
        self.assertEqual(skipped, 0)
        assigned, skipped = assignment_services.assign_students_to_project(self.teacher, proj, [self.student.id])
        self.assertEqual(assigned, 0)
        self.assertEqual(skipped, 1)

        # 4. Invalid assignment state transition
        asgn = ProjectAssignment.objects.get(project=proj, student=self.student)
        with self.assertRaises(assignment_services.InvalidTransition):
            assignment_services.transition(asgn, AssignmentStatus.EVALUATED)

        # 5. Query student assignments
        student_asgns = assignment_services.get_student_assignments(self.student, status=AssignmentStatus.ASSIGNED)
        self.assertEqual(student_asgns.count(), 1)
        fetched_asgn = assignment_services.get_student_assignment_or_404(asgn.id, self.student)
        self.assertEqual(fetched_asgn.id, asgn.id)

        with self.assertRaises(Http404):
            assignment_services.get_student_assignment_or_404(999999, self.student)

        # 6. Mark overdue assignments
        asgn.status = AssignmentStatus.IN_PROGRESS
        asgn.save()
        proj.deadline = self.now - timedelta(days=2)
        proj.save()
        overdue_count = assignment_services.mark_overdue_assignments(now=self.now)
        self.assertGreaterEqual(overdue_count, 1)
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.OVERDUE)

        # 7. Deadline reminders
        proj.deadline = self.now + timedelta(hours=24)
        proj.save()
        asgn.status = AssignmentStatus.IN_PROGRESS
        asgn.deadline_reminder_sent = False
        asgn.save()
        reminded_count = assignment_services.send_deadline_reminders(now=self.now)
        self.assertGreaterEqual(reminded_count, 1)
        asgn.refresh_from_db()
        self.assertTrue(asgn.deadline_reminder_sent)

    # --- submissions/services.py ---
    def test_submissions_services_edge_cases(self):
        # 1. sanitise_filename
        self.assertEqual(submission_services.sanitise_filename(""), "unnamed_file")
        self.assertEqual(submission_services.sanitise_filename(None), "unnamed_file")
        self.assertEqual(submission_services.sanitise_filename("../../hack.sh"), "hack.sh")

        # 2. File validation checks
        empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            submission_services.validate_uploaded_file(empty_file)

        large_file = SimpleUploadedFile(
            "big.pdf", b"%PDF-1.4\n" + b"A" * 15 * 1024 * 1024, content_type="application/pdf"
        )
        with self.assertRaises(ValidationError):
            submission_services.validate_uploaded_file(large_file)

        unsupported_file = SimpleUploadedFile("audio.mp3", b"ID3\x03\x00\x00\x00", content_type="audio/mp3")
        with self.assertRaises(ValidationError):
            submission_services.validate_uploaded_file(unsupported_file)

        # PE binary disguised as PDF
        pe_file = SimpleUploadedFile("malware.pdf", b"MZ\x90\x00\x03\x00\x00\x00", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            submission_services.validate_uploaded_file(pe_file)

        # 3. submit_file
        proj = project_services.create_project(self.teacher, "Sub Proj", "Desc", self.now + timedelta(days=5))
        assignment_services.assign_students_to_project(self.teacher, proj, [self.student.id])
        asgn = ProjectAssignment.objects.get(project=proj, student=self.student)

        # Non-student submit
        pdf_file = SimpleUploadedFile("test.pdf", b"%PDF-1.4\ncontent\n%%EOF", content_type="application/pdf")
        with self.assertRaises(Http404):
            submission_services.submit_file(asgn, pdf_file, self.teacher)

        # Submit while in disallowed status
        asgn.status = AssignmentStatus.EVALUATED
        asgn.save()
        with self.assertRaises(ValidationError):
            submission_services.submit_file(asgn, pdf_file, self.student)

        # Successful submit in Revision Requested
        asgn.status = AssignmentStatus.REVISION_REQUESTED
        asgn.save()
        sub = submission_services.submit_file(asgn, pdf_file, self.student)
        self.assertIsNotNone(sub.id)
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.SUBMITTED)

        # 4. Teacher opens submission
        opened_sub = submission_services.teacher_open_submission(sub.id, self.teacher)
        self.assertEqual(opened_sub.id, sub.id)
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.UNDER_REVIEW)

        with self.assertRaises(Http404):
            submission_services.teacher_open_submission(999999, self.teacher)

        with self.assertRaises(Http404):
            submission_services.teacher_open_submission(sub.id, self.other_teacher)

        # 5. Download authorization
        sub_obj, path = submission_services.get_submission_for_download(sub.id, self.student)
        self.assertTrue(os.path.exists(path))

        with self.assertRaises(Http404):
            submission_services.get_submission_for_download(999999, self.student)

    # --- reviews/services.py ---
    def test_reviews_services_edge_cases(self):
        proj = project_services.create_project(self.teacher, "Review Edge Cases", "Desc", self.now + timedelta(days=5))
        assignment_services.assign_students_to_project(self.teacher, proj, [self.student.id])
        asgn = ProjectAssignment.objects.get(project=proj, student=self.student)
        pdf_file = SimpleUploadedFile("rev.pdf", b"%PDF-1.4\ncontent\n%%EOF", content_type="application/pdf")
        sub = submission_services.submit_file(asgn, pdf_file, self.student)

        # 1. Non-teacher gives feedback
        with self.assertRaises(PermissionDenied):
            reviews_services.give_feedback(sub, self.student, "Nice work")

        # 2. Other teacher gives feedback
        with self.assertRaises(Http404):
            reviews_services.give_feedback(sub, self.other_teacher, "Nice work")

        # 3. Teacher gives empty comments
        with self.assertRaises(ValidationError):
            reviews_services.give_feedback(sub, self.teacher, "   ")

        # 4. Give feedback with revision request
        fb = reviews_services.give_feedback(sub, self.teacher, "Please revise section 3.", request_revision=True)
        self.assertEqual(fb.comments, "Please revise section 3.")
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.REVISION_REQUESTED)

        # 5. Assign marks validations
        with self.assertRaises(PermissionDenied):
            reviews_services.assign_marks(asgn, self.student, 90.0, 100.0)

        with self.assertRaises(Http404):
            reviews_services.assign_marks(asgn, self.other_teacher, 90.0, 100.0)

        # Assignment in REVISION_REQUESTED cannot be directly graded
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, 90.0, 100.0)

        # Resubmit & open to set to UNDER_REVIEW
        pdf_file2 = SimpleUploadedFile("rev2.pdf", b"%PDF-1.4\ncontent v2\n%%EOF", content_type="application/pdf")
        sub2 = submission_services.submit_file(asgn, pdf_file2, self.student)
        submission_services.teacher_open_submission(sub2, self.teacher)
        asgn.refresh_from_db()

        # Score validation
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, -5, 100)
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, 105, 100)
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, 50, 0)
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, "invalid_num", 100)

        # Successful grading
        marks = reviews_services.assign_marks(asgn, self.teacher, 85, 100)
        self.assertEqual(marks.score, Decimal(85))
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.EVALUATED)
        proj.refresh_from_db()
        self.assertEqual(proj.status, ProjectStatus.CLOSED)

        # Cannot assign marks to closed project
        with self.assertRaises(ValidationError):
            reviews_services.assign_marks(asgn, self.teacher, 90, 100)

        # 6. Student views feedback & marks
        feedbacks = reviews_services.get_student_feedbacks(self.student, assignment_id=asgn.id)
        self.assertEqual(feedbacks.count(), 1)

        with self.assertRaises(PermissionDenied):
            reviews_services.get_student_feedbacks(self.teacher)

        with self.assertRaises(Http404):
            reviews_services.get_student_feedbacks(self.student, assignment_id=999999)

        student_mark = reviews_services.get_student_marks(self.student, assignment_id=asgn.id)
        self.assertEqual(student_mark.score, Decimal(85))

        with self.assertRaises(PermissionDenied):
            reviews_services.get_student_marks(self.teacher)

        # 7. Generate marks CSV
        csv_str = reviews_services.generate_marks_csv(proj, self.teacher)
        self.assertIn("Academic Project Management System - Marks Report", csv_str)
        self.assertIn(self.student.name, csv_str)

        with self.assertRaises(Http404):
            reviews_services.generate_marks_csv(proj, self.other_teacher)

    # --- progress/services.py ---
    def test_progress_services_edge_cases(self):
        proj = project_services.create_project(self.teacher, "Progress Proj", "Desc", self.now + timedelta(days=5))
        assignment_services.assign_students_to_project(self.teacher, proj, [self.student.id])
        asgn = ProjectAssignment.objects.get(project=proj, student=self.student)

        # 1. Non-student update
        with self.assertRaises(Http404):
            progress_services.add_progress_update(self.teacher, asgn, 10, "Attempt")

        # 2. Percentage range validation
        with self.assertRaises(ValidationError):
            progress_services.add_progress_update(self.student, asgn, -1, "Negative")
        with self.assertRaises(ValidationError):
            progress_services.add_progress_update(self.student, asgn, 101, "Over 100")
        with self.assertRaises(ValidationError):
            progress_services.add_progress_update(self.student, asgn, "abc", "String")

        # 3. Valid update (transitions Assigned -> In progress)
        up1 = progress_services.add_progress_update(self.student, asgn, 30, "Initial progress")
        self.assertEqual(up1.percent_complete, 30)
        asgn.refresh_from_db()
        self.assertEqual(asgn.status, AssignmentStatus.IN_PROGRESS)

        # 4. Cannot decrease progress percentage
        with self.assertRaises(ValidationError):
            progress_services.add_progress_update(self.student, asgn, 25, "Decrease")

        # 5. Disallowed once evaluated
        asgn.status = AssignmentStatus.EVALUATED
        asgn.save()
        with self.assertRaises(ValidationError):
            progress_services.add_progress_update(self.student, asgn, 50, "Late")

        # 6. Progress summary & CSV report
        asgn.status = AssignmentStatus.IN_PROGRESS
        asgn.save()
        summary = progress_services.get_progress_summary(self.teacher, project_id=proj.id)
        self.assertEqual(len(summary), 1)

        report = progress_services.get_project_progress_report(self.teacher, proj.id)
        self.assertEqual(report["avg_completion"], 30.0)

        csv_str = progress_services.generate_progress_csv_report(self.teacher, proj.id)
        self.assertIn("Student Name", csv_str)
        self.assertIn("30%", csv_str)

        with self.assertRaises(Http404):
            progress_services.get_project_progress_report(self.other_teacher, proj.id)

    # --- dashboard/services.py ---
    def test_dashboard_services_edge_cases(self):
        # 1. Non-student accesses student dashboard
        with self.assertRaises(PermissionDenied):
            dashboard_services.get_student_dashboard_data(self.teacher)

        # 2. Non-teacher accesses teacher dashboard
        with self.assertRaises(PermissionDenied):
            dashboard_services.get_teacher_dashboard_data(self.student)

        # 3. Data generation
        teacher_dash = dashboard_services.get_teacher_dashboard_data(self.teacher)
        self.assertIn("chart_labels", teacher_dash)
        self.assertIn("chart_data", teacher_dash)

        student_dash = dashboard_services.get_student_dashboard_data(self.student)
        self.assertIn("status_counts", student_dash)

        # 4. Notification operations
        notif1 = Notification.objects.create(user=self.student, message="Alert 1", link="/dashboard/")
        notif2 = Notification.objects.create(user=self.student, message="Alert 2", link="/dashboard/")
        self.assertEqual(dashboard_services.get_user_notifications(self.student).count(), 2)

        dashboard_services.mark_notification_as_read(self.student, notif1.id)
        notif1.refresh_from_db()
        self.assertTrue(notif1.is_read)

        dashboard_services.mark_all_notifications_as_read(self.student)
        notif2.refresh_from_db()
        self.assertTrue(notif2.is_read)

        # Non-existent notification ID raises Http404
        with self.assertRaises(Http404):
            dashboard_services.mark_notification_as_read(self.student, 999999)
