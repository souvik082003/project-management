import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserRole
from accounts.services import register_user
from assignments.models import AssignmentStatus, ProjectAssignment
from assignments.services import assign_students_to_project, transition
from projects.services import create_project
from submissions.models import Submission
from submissions.services import (
    get_submission_for_download,
    sanitise_filename,
    submit_file,
    teacher_open_submission,
)


class SubmissionTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.temp_media = tempfile.mkdtemp()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_media, ignore_errors=True)
        super().tearDownClass()

    def tearDown(self):
        for item in os.listdir(self.temp_media):
            item_path = os.path.join(self.temp_media, item)
            if os.path.isdir(item_path):
                shutil.rmtree(item_path, ignore_errors=True)
            elif os.path.isfile(item_path):
                os.remove(item_path)
        super().tearDown()

    def setUp(self):
        self.teacher_1 = register_user(
            name="Teacher One",
            email="teacher.one@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-01",
        )
        self.teacher_2 = register_user(
            name="Teacher Two",
            email="teacher.two@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-02",
        )
        self.student_1 = register_user(
            name="Student Alice",
            email="alice@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="ALICE-01",
        )
        self.student_2 = register_user(
            name="Student Bob",
            email="bob@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="BOB-02",
        )
        self.future_deadline = timezone.now() + timedelta(days=7)
        self.project = create_project(
            teacher=self.teacher_1,
            title="Operating Systems Project",
            description="Build scheduler",
            deadline=self.future_deadline,
        )
        assign_students_to_project(self.teacher_1, self.project, [self.student_1.id])
        self.assignment_1 = ProjectAssignment.objects.get(project=self.project, student=self.student_1)

    def test_valid_pdf_accepted(self):
        """Valid PDF deliverable is accepted, versioned, and transitions to Submitted."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\n%test content\n%%EOF"
            upload = SimpleUploadedFile("report.pdf", pdf_content, content_type="application/pdf")

            submission = submit_file(self.assignment_1, upload, self.student_1)
            self.assertEqual(submission.version, 1)
            self.assertEqual(submission.file_name, "report.pdf")
            self.assertTrue(os.path.exists(os.path.join(self.temp_media, submission.file_path)))

            self.assignment_1.refresh_from_db()
            self.assertEqual(self.assignment_1.status, AssignmentStatus.SUBMITTED)

    def test_exe_rejected(self):
        """Executable file is rejected by extension check."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            exe_content = b"MZ\x90\x00some binary content"
            upload = SimpleUploadedFile("payload.exe", exe_content, content_type="application/x-msdownload")

            with self.assertRaises(ValidationError) as ctx:
                submit_file(self.assignment_1, upload, self.student_1)
            self.assertIn("file", ctx.exception.message_dict)

    def test_renamed_exe_to_pdf_rejected_by_content_check(self):
        """An executable disguised as a PDF (starts with MZ) is rejected by signature check."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            fake_pdf_content = b"MZ\x90\x00this is an exe disguised as pdf"
            upload = SimpleUploadedFile("fake.pdf", fake_pdf_content, content_type="application/pdf")

            with self.assertRaises(ValidationError) as ctx:
                submit_file(self.assignment_1, upload, self.student_1)
            self.assertIn("file", ctx.exception.message_dict)

    def test_oversize_rejected(self):
        """File larger than MAX_UPLOAD_SIZE is rejected."""
        # Override limit to 100 bytes for test
        with override_settings(MEDIA_ROOT=self.temp_media, MAX_UPLOAD_SIZE=100):
            big_content = b"%PDF-1.4\n" + (b"A" * 200)
            upload = SimpleUploadedFile("big.pdf", big_content, content_type="application/pdf")

            with self.assertRaises(ValidationError) as ctx:
                submit_file(self.assignment_1, upload, self.student_1)
            self.assertIn("file", ctx.exception.message_dict)

    def test_empty_file_rejected(self):
        """Empty file (0 bytes) is rejected."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            upload = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
            with self.assertRaises(ValidationError) as ctx:
                submit_file(self.assignment_1, upload, self.student_1)
            self.assertIn("file", ctx.exception.message_dict)

    def test_path_traversal_filename_sanitised(self):
        """Malicious filename with path traversal characters is sanitised."""
        raw = "../../../etc/passwd.pdf"
        sanitised = sanitise_filename(raw)
        self.assertNotIn("/", sanitised)
        self.assertNotIn("..", sanitised)
        self.assertEqual(sanitised, "passwd.pdf")

    def test_version_increments_on_resubmission(self):
        """Resubmitting a file increments the version number."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\nInitial draft\n%%EOF"
            upload_1 = SimpleUploadedFile("v1.pdf", pdf_content, content_type="application/pdf")
            sub_1 = submit_file(self.assignment_1, upload_1, self.student_1)
            self.assertEqual(sub_1.version, 1)

            # Resubmission (e.g. after teacher requests revision)
            transition(self.assignment_1, AssignmentStatus.UNDER_REVIEW)
            transition(self.assignment_1, AssignmentStatus.REVISION_REQUESTED)

            pdf_content_2 = b"%PDF-1.4\nRevised draft\n%%EOF"
            upload_2 = SimpleUploadedFile("v2.pdf", pdf_content_2, content_type="application/pdf")
            sub_2 = submit_file(self.assignment_1, upload_2, self.student_1)
            self.assertEqual(sub_2.version, 2)
            self.assertEqual(self.assignment_1.submissions.count(), 2)

    def test_failure_leaves_no_orphan_row_or_file(self):
        """If database creation fails, the saved disk file is cleanly removed."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\ntest failure\n%%EOF"
            upload = SimpleUploadedFile("fail.pdf", pdf_content, content_type="application/pdf")

            with patch("submissions.models.Submission.objects.create", side_effect=RuntimeError("Simulated DB Crash")):
                with self.assertRaises(RuntimeError):
                    submit_file(self.assignment_1, upload, self.student_1)

            # Verify no DB row
            self.assertEqual(Submission.objects.count(), 0)
            # Verify no orphan file in temp_media
            upload_dir = os.path.join(self.temp_media, "uploads", str(self.assignment_1.id))
            if os.path.exists(upload_dir):
                self.assertEqual(len(os.listdir(upload_dir)), 0)

    def test_wrong_student_cannot_submit(self):
        """Student cannot submit on an assignment that does not belong to them."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\ntest\n%%EOF"
            upload = SimpleUploadedFile("wrong.pdf", pdf_content, content_type="application/pdf")

            from django.http import Http404

            with self.assertRaises(Http404):
                submit_file(self.assignment_1, upload, self.student_2)

    def test_opening_submission_transitions_to_under_review(self):
        """Teacher opening a submission moves assignment from Submitted -> Under review."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\nreport\n%%EOF"
            upload = SimpleUploadedFile("report.pdf", pdf_content, content_type="application/pdf")
            submission = submit_file(self.assignment_1, upload, self.student_1)
            self.assertEqual(self.assignment_1.status, AssignmentStatus.SUBMITTED)

            # Teacher opens submission
            teacher_open_submission(submission, self.teacher_1)
            self.assignment_1.refresh_from_db()
            self.assertEqual(self.assignment_1.status, AssignmentStatus.UNDER_REVIEW)

    def test_download_permissions(self):
        """Own student and creator teacher can download; unauthorized users are denied."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\ndownloadable\n%%EOF"
            upload = SimpleUploadedFile("secure.pdf", pdf_content, content_type="application/pdf")
            sub = submit_file(self.assignment_1, upload, self.student_1)

            # 1. Own student can download
            sub_obj, path = get_submission_for_download(sub.id, self.student_1)
            self.assertEqual(sub_obj.id, sub.id)

            # 2. Other student denied
            with self.assertRaises(PermissionDenied):
                get_submission_for_download(sub.id, self.student_2)

            # 3. Creator teacher can download
            sub_obj_t, path_t = get_submission_for_download(sub.id, self.teacher_1)
            self.assertEqual(sub_obj_t.id, sub.id)

            # 4. Other teacher denied with 404
            from django.http import Http404

            with self.assertRaises(Http404):
                get_submission_for_download(sub.id, self.teacher_2)

    def test_late_submission_from_overdue_works_and_shows_late_badge(self):
        """Late submission from Overdue state is accepted and flagged as late."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            # Transition to In progress then Overdue
            transition(self.assignment_1, AssignmentStatus.IN_PROGRESS)
            transition(self.assignment_1, AssignmentStatus.OVERDUE)

            # Simulate past deadline
            past_time = timezone.now() - timedelta(days=2)
            from projects.models import Project

            Project.objects.filter(pk=self.project.pk).update(deadline=past_time)
            self.project.refresh_from_db()

            pdf_content = b"%PDF-1.4\nlate work\n%%EOF"
            upload = SimpleUploadedFile("late.pdf", pdf_content, content_type="application/pdf")
            sub = submit_file(self.assignment_1, upload, self.student_1)

            self.assignment_1.refresh_from_db()
            self.assertEqual(self.assignment_1.status, AssignmentStatus.SUBMITTED)
            self.assertTrue(sub.is_late)

    def test_notification_failure_does_not_break_submission(self):
        """If notification delivery throws an exception, file submission still succeeds."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_content = b"%PDF-1.4\ncontent\n%%EOF"
            upload = SimpleUploadedFile("notify.pdf", pdf_content, content_type="application/pdf")

            with patch(
                "submissions.services.notify_teacher_new_submission", side_effect=RuntimeError("SMTP Server Down")
            ):
                submission = submit_file(self.assignment_1, upload, self.student_1)
                self.assertIsNotNone(submission.pk)
                self.assertEqual(submission.version, 1)

    def test_web_upload_and_download_views(self):
        """Test web controllers for student uploading and teacher downloading."""
        with override_settings(MEDIA_ROOT=self.temp_media):
            self.client.force_login(self.student_1)

            # Student uploads via POST
            pdf_content = b"%PDF-1.4\nweb upload\n%%EOF"
            upload = SimpleUploadedFile("web_report.pdf", pdf_content, content_type="application/pdf")
            post_resp = self.client.post(
                reverse("submissions:upload_submission", kwargs={"assignment_id": self.assignment_1.pk}),
                {"file": upload},
            )
            self.assertRedirects(
                post_resp, reverse("submissions:upload_submission", kwargs={"assignment_id": self.assignment_1.pk})
            )
            submission = Submission.objects.get(file_name="web_report.pdf")

            # Teacher opens detail view (transitions Submitted -> Under review)
            self.client.force_login(self.teacher_1)
            detail_resp = self.client.get(
                reverse("submissions:submission_detail", kwargs={"submission_id": submission.pk})
            )
            self.assertEqual(detail_resp.status_code, 200)
            self.assertContains(detail_resp, "web_report.pdf")
            self.assignment_1.refresh_from_db()
            self.assertEqual(self.assignment_1.status, AssignmentStatus.UNDER_REVIEW)

            # Teacher downloads file
            download_resp = self.client.get(
                reverse("submissions:download_submission", kwargs={"submission_id": submission.pk})
            )
            self.assertEqual(download_resp.status_code, 200)
            self.assertEqual(download_resp["Content-Disposition"], 'attachment; filename="web_report.pdf"')
