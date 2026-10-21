import os
import shutil
import tempfile
from datetime import timedelta
from unittest.mock import patch

from django.core import mail
from django.core.exceptions import PermissionDenied
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserRole
from accounts.services import register_user
from assignments.models import AssignmentStatus, ProjectAssignment
from assignments.services import (
    assign_students_to_project,
    send_deadline_reminders,
)
from dashboard.models import Notification
from dashboard.services import (
    get_student_dashboard_data,
    get_teacher_dashboard_data,
    mark_all_notifications_as_read,
    mark_notification_as_read,
)
from projects.services import create_project
from reviews.services import assign_marks, give_feedback
from submissions.services import submit_file, teacher_open_submission


class DashboardAndNotificationsTests(TestCase):
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
        self.teacher = register_user(
            name="Professor Smith",
            email="prof.smith@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-PROF-01",
        )
        self.student = register_user(
            name="Charlie Brown",
            email="charlie@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="STU-01",
        )
        self.student_2 = register_user(
            name="Dana White",
            email="dana@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="STU-02",
        )

        self.project = create_project(
            teacher=self.teacher,
            title="Distributed Raft Node",
            description="Consensus engine implementation",
            deadline=timezone.now() + timedelta(days=10),
        )
        # Clear outbox
        mail.outbox.clear()

    def _create_submission(self, assignment, student, filename="raft.pdf"):
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_bytes = b"%PDF-1.4\ncontent\n%%EOF"
            upload = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
            return submit_file(assignment, upload, student)

    def test_notification_on_assignment_allocation(self):
        """Assigning a student dispatches an email and creates an in-app notification."""
        assign_students_to_project(self.teacher, self.project, [self.student.id])

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.student.email, email.to)
        self.assertEqual(email.subject, f"New Project Assigned: {self.project.title}")
        self.assertIn(self.project.title, email.body)

        # In-app alert check
        notif = Notification.objects.filter(user=self.student).first()
        self.assertIsNotNone(notif)
        self.assertFalse(notif.is_read)
        self.assertIn(self.project.title, notif.message)

    def test_notification_on_student_submission(self):
        """Student deliverable submission emails supervising teacher and creates in-app notification."""
        assign_students_to_project(self.teacher, self.project, [self.student.id])
        mail.outbox.clear()

        assign = ProjectAssignment.objects.get(project=self.project, student=self.student)
        sub = self._create_submission(assign, self.student, "raft_v1.pdf")

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.teacher.email, email.to)
        self.assertEqual(email.subject, f"New Submission (v1): {self.project.title}")

        # In-app alert for teacher
        notif = Notification.objects.filter(user=self.teacher).first()
        self.assertIsNotNone(notif)
        self.assertIn("v1", notif.message)

    def test_notification_on_teacher_feedback(self):
        """Teacher feedback triggers email and in-app alert for the student."""
        assign_students_to_project(self.teacher, self.project, [self.student.id])
        assign = ProjectAssignment.objects.get(project=self.project, student=self.student)
        sub = self._create_submission(assign, self.student)
        teacher_open_submission(sub, self.teacher)
        mail.outbox.clear()

        give_feedback(sub, self.teacher, "Great progress on heartbeat protocol.", request_revision=False)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.student.email, email.to)
        self.assertEqual(email.subject, f"Feedback on Submission (v1): {self.project.title}")
        self.assertIn("Great progress", email.body)

        # In-app alert for student
        notif = Notification.objects.filter(user=self.student).order_by("-created_at").first()
        self.assertIn("feedback given", notif.message.lower())

    def test_notification_on_marks_published(self):
        """Marking an assignment sends grade notification to student."""
        assign_students_to_project(self.teacher, self.project, [self.student.id])
        assign = ProjectAssignment.objects.get(project=self.project, student=self.student)
        sub = self._create_submission(assign, self.student)
        teacher_open_submission(sub, self.teacher)
        mail.outbox.clear()

        assign_marks(assign, self.teacher, score=88, max_score=100)

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertIn(self.student.email, email.to)
        self.assertEqual(email.subject, f"Evaluation Completed: Marks Published for {self.project.title}")
        self.assertIn("88", email.body)

        # In-app alert for student
        notif = Notification.objects.filter(user=self.student).order_by("-created_at").first()
        self.assertIn("88", notif.message)

    def test_email_failure_does_not_break_assignment_submission_feedback_or_marks(self):
        """Mocking send_mail failure guarantees business operations proceed uninterrupted."""
        with patch("django.core.mail.send_mail", side_effect=RuntimeError("SMTP Down")):
            # 1. Assignment
            assign_students_to_project(self.teacher, self.project, [self.student.id])
            assign = ProjectAssignment.objects.get(project=self.project, student=self.student)
            self.assertIsNotNone(assign.id)

            # 2. Submission
            sub = self._create_submission(assign, self.student)
            self.assertIsNotNone(sub.id)

            # 3. Feedback
            teacher_open_submission(sub, self.teacher)
            fb = give_feedback(sub, self.teacher, "Feedback despite SMTP outage")
            self.assertIsNotNone(fb.id)

            # 4. Marks
            marks = assign_marks(assign, self.teacher, score=90, max_score=100)
            self.assertIsNotNone(marks.id)

    def test_dashboard_counts_correct_per_role(self):
        """Both student and teacher dashboard aggregators return precise metrics."""
        assign_students_to_project(self.teacher, self.project, [self.student.id, self.student_2.id])
        assign_1 = ProjectAssignment.objects.get(project=self.project, student=self.student)
        assign_2 = ProjectAssignment.objects.get(project=self.project, student=self.student_2)

        # Student 1 submits
        sub1 = self._create_submission(assign_1, self.student)

        # Verify Teacher Dashboard Data
        teacher_data = get_teacher_dashboard_data(self.teacher)
        self.assertEqual(teacher_data["total_projects"], 1)
        self.assertEqual(teacher_data["total_students_assigned"], 2)
        self.assertEqual(teacher_data["submissions_waiting"].count(), 1)
        self.assertEqual(teacher_data["status_counts"][AssignmentStatus.SUBMITTED], 1)
        self.assertEqual(teacher_data["status_counts"][AssignmentStatus.ASSIGNED], 1)

        # Verify Student Dashboard Data
        student_data = get_student_dashboard_data(self.student)
        self.assertEqual(student_data["total_assignments"], 1)
        self.assertEqual(student_data["status_counts"][AssignmentStatus.SUBMITTED], 1)

    def test_student_cannot_see_teacher_dashboard_data(self):
        """Student attempting to call teacher metrics or view teacher controls is blocked."""
        with self.assertRaises(PermissionDenied):
            get_teacher_dashboard_data(self.student)

        self.client.force_login(self.student)
        resp = self.client.get(reverse("dashboard:dashboard"))
        self.assertEqual(resp.status_code, 200)
        # Verify student template is rendered, not teacher supervisory controls
        self.assertContains(resp, "Student Dashboard")
        self.assertNotContains(resp, "Teacher Supervisory Dashboard")

    def test_deadline_reminders_command_emails_only_right_students_once(self):
        """send_deadline_reminders emails students whose deadline is within 2 days, exactly once."""
        # Project 1: Deadline in 30 hours (due within 2 days)
        proj_soon = create_project(
            teacher=self.teacher,
            title="Urgent Project",
            description="Due soon",
            deadline=timezone.now() + timedelta(hours=30),
        )
        assign_students_to_project(self.teacher, proj_soon, [self.student.id])

        # Project 2: Deadline in 6 days (not due soon)
        proj_far = create_project(
            teacher=self.teacher,
            title="Far Away Project",
            description="Due later",
            deadline=timezone.now() + timedelta(days=6),
        )
        assign_students_to_project(self.teacher, proj_far, [self.student_2.id])

        mail.outbox.clear()

        # Run command 1st time
        sent_count = send_deadline_reminders()
        self.assertEqual(sent_count, 1)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn(self.student.email, mail.outbox[0].to)
        self.assertIn("Urgent Project", mail.outbox[0].subject)

        # Run command 2nd time: should NOT email again (reminder sent once)
        sent_count_2 = send_deadline_reminders()
        self.assertEqual(sent_count_2, 0)
        self.assertEqual(len(mail.outbox), 1)

    def test_unread_count_and_mark_read_view(self):
        """In-app notifications unread counter increments and decrements on read."""
        notif = Notification.objects.create(user=self.student, message="Test notification alert", link="/dashboard/")
        self.assertEqual(self.student.notifications.filter(is_read=False).count(), 1)

        # Mark single as read
        mark_notification_as_read(self.student, notif.id)
        self.assertEqual(self.student.notifications.filter(is_read=False).count(), 0)

        # Test mark all as read
        Notification.objects.create(user=self.student, message="Alert 1")
        Notification.objects.create(user=self.student, message="Alert 2")
        self.assertEqual(self.student.notifications.filter(is_read=False).count(), 2)

        mark_all_notifications_as_read(self.student)
        self.assertEqual(self.student.notifications.filter(is_read=False).count(), 0)
