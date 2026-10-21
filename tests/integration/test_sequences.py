"""
Integration tests for the three design sequences and the full end-to-end workflow:
1. Sequence 1: Authentication and Login Protection.
2. Sequence 2: Deliverable Submission & Teacher Inspection.
3. Sequence 3: Feedback, Revisions, and Marks Evaluation.
4. Sequence 4: Full End-to-End Master Academic Lifecycle.
"""

import os
import shutil
import tempfile
from datetime import timedelta

from django.core import mail
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from progress import services as progress_services
from projects import services as project_services
from projects.models import ProjectStatus
from reviews import services as reviews_services
from submissions import services as submission_services


class TestIntegrationSequences(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        )
        self.settings_override.enable()

        self.client = Client()
        self.now = timezone.now()

        # Seed users
        self.teacher = User.objects.create_user(
            username="prof.test@example.edu",
            email="prof.test@example.edu",
            password="TeacherPass@123",
            name="Prof. Test Supervisor",
            role=UserRole.TEACHER,
            department="CSE",
            employee_id="T001",
        )

        self.student_1 = User.objects.create_user(
            username="student1@example.edu",
            email="student1@example.edu",
            password="StudentPass@123",
            name="Student One",
            role=UserRole.STUDENT,
            department="CSE",
            roll_no="S001",
        )

        self.student_2 = User.objects.create_user(
            username="student2@example.edu",
            email="student2@example.edu",
            password="StudentPass@123",
            name="Student Two",
            role=UserRole.STUDENT,
            department="CSE",
            roll_no="S002",
        )

    def tearDown(self):
        self.settings_override.disable()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_sequence_1_login_and_lockout(self):
        """
        Sequence 1: Login workflow and brute-force lockout.
        """
        # 1. Invalid password increases attempt counter
        res = self.client.post(
            reverse("accounts:login"), {"email": self.student_1.email, "password": "WrongPassword@999"}
        )
        self.assertEqual(res.status_code, 200)
        self.student_1.refresh_from_db()
        self.assertEqual(self.student_1.failed_login_attempts, 1)

        # 2. Trigger lockout on 5 consecutive failures
        for _ in range(4):
            self.client.post(
                reverse("accounts:login"), {"email": self.student_1.email, "password": "WrongPassword@999"}
            )
        self.student_1.refresh_from_db()
        self.assertEqual(self.student_1.failed_login_attempts, 5)
        self.assertTrue(self.student_1.is_locked)

        # 3. Valid password rejected while locked
        res_locked = self.client.post(
            reverse("accounts:login"), {"email": self.student_1.email, "password": "StudentPass@123"}
        )
        self.assertContains(res_locked, "temporarily locked")

        # 4. Successful login for teacher with correct credentials
        res_teacher = self.client.post(
            reverse("accounts:login"), {"email": self.teacher.email, "password": "TeacherPass@123"}, follow=True
        )
        self.assertRedirects(res_teacher, reverse("dashboard:dashboard"))
        self.assertContains(res_teacher, "Prof. Test Supervisor")

    def test_sequence_2_submit_file_and_teacher_inspection(self):
        """
        Sequence 2: Assign -> Progress update -> Deliverable Upload -> Teacher Inspection.
        """
        # 1. Teacher creates project and assigns student
        project = project_services.create_project(
            teacher=self.teacher,
            title="Real-Time Operating System",
            description="Kernel thread scheduler implementation.",
            deadline=self.now + timedelta(days=10),
        )
        assignment_services.assign_students_to_project(self.teacher, project, [self.student_1.id])
        assignment = ProjectAssignment.objects.get(project=project, student=self.student_1)
        self.assertEqual(assignment.status, AssignmentStatus.ASSIGNED)

        # 2. Student updates milestone progress
        progress_services.add_progress_update(
            student=self.student_1,
            assignment=assignment,
            percent_complete=50,
            remarks="Scheduler design document drafted.",
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.IN_PROGRESS)

        # 3. Student uploads deliverable
        mail.outbox.clear()
        pdf_file = SimpleUploadedFile(
            "kernel_report.pdf", b"%PDF-1.4\n%Report content\n%%EOF", content_type="application/pdf"
        )
        submission = submission_services.submit_file(assignment=assignment, uploaded_file=pdf_file, user=self.student_1)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.SUBMITTED)
        self.assertEqual(submission.version, 1)
        self.assertTrue(os.path.exists(os.path.join(self.temp_media, submission.file_path)))

        # Email sent to supervising teacher
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("New Submission (v1)", mail.outbox[0].subject)

        # 4. Teacher opens submission
        self.client.force_login(self.teacher)
        res_detail = self.client.get(reverse("submissions:submission_detail", kwargs={"submission_id": submission.id}))
        self.assertEqual(res_detail.status_code, 200)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.UNDER_REVIEW)

    def test_sequence_3_feedback_revision_and_evaluation(self):
        """
        Sequence 3: Teacher Review -> Request Revision -> Resubmit v2 -> Grade Marks -> Project Close.
        """
        # Set up project, assignment, and initial submission
        project = project_services.create_project(
            teacher=self.teacher,
            title="Database Query Optimizer",
            description="Cost-based query optimizer for relational engine.",
            deadline=self.now + timedelta(days=7),
        )
        assignment_services.assign_students_to_project(self.teacher, project, [self.student_1.id])
        assignment = ProjectAssignment.objects.get(project=project, student=self.student_1)

        pdf_v1 = SimpleUploadedFile("optimizer_v1.pdf", b"%PDF-1.4\nv1 content\n%%EOF", content_type="application/pdf")
        sub_v1 = submission_services.submit_file(assignment, pdf_v1, self.student_1)

        # Teacher opens submission
        submission_services.teacher_open_submission(sub_v1.id, self.teacher)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.UNDER_REVIEW)

        # 1. Teacher gives feedback requesting revision
        mail.outbox.clear()
        feedback = reviews_services.give_feedback(
            submission=sub_v1,
            teacher=self.teacher,
            comments="Please implement B-Tree index scan cost estimation.",
            request_revision=True,
        )
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.REVISION_REQUESTED)
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Feedback on Submission (v1)", mail.outbox[0].subject)

        # 2. Student uploads Version 2 deliverable
        pdf_v2 = SimpleUploadedFile(
            "optimizer_v2.pdf", b"%PDF-1.4\nv2 content with B-Tree cost\n%%EOF", content_type="application/pdf"
        )
        sub_v2 = submission_services.submit_file(assignment, pdf_v2, self.student_1)
        self.assertEqual(sub_v2.version, 2)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.SUBMITTED)

        # Teacher opens v2
        submission_services.teacher_open_submission(sub_v2, self.teacher)
        assignment.refresh_from_db()
        self.assertEqual(assignment.status, AssignmentStatus.UNDER_REVIEW)

        # 3. Teacher assigns final marks
        mail.outbox.clear()
        marks = reviews_services.assign_marks(assignment=assignment, teacher=self.teacher, score=95.0, max_score=100.0)
        assignment.refresh_from_db()
        project.refresh_from_db()

        self.assertEqual(assignment.status, AssignmentStatus.EVALUATED)
        self.assertEqual(project.status, ProjectStatus.CLOSED)
        self.assertEqual(marks.percentage, 95.0)
        self.assertTrue(marks.is_pass)

        # Student notification sent
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Evaluation Completed", mail.outbox[0].subject)

    def test_sequence_4_full_master_end_to_end_workflow(self):
        """
        Sequence 4: Complete multi-student lifecycle:
        Project creation -> multi-student assignment -> parallel updates ->
        grading all students -> auto closure -> statistical report verification.
        """
        # Step 1: Teacher creates project
        project = project_services.create_project(
            teacher=self.teacher,
            title="Distributed Consensus Engine",
            description="Raft-based consensus implementation.",
            deadline=self.now + timedelta(days=14),
        )
        self.assertEqual(project.status, ProjectStatus.DRAFT)

        # Step 2: Assign two students
        assignment_services.assign_students_to_project(self.teacher, project, [self.student_1.id, self.student_2.id])
        project.refresh_from_db()
        self.assertEqual(project.status, ProjectStatus.ASSIGNED)

        asgn_1 = ProjectAssignment.objects.get(project=project, student=self.student_1)
        asgn_2 = ProjectAssignment.objects.get(project=project, student=self.student_2)

        # Step 3: Student 1 progress updates & submits
        progress_services.add_progress_update(self.student_1, asgn_1, 50, "Log replication done.")
        pdf_1 = SimpleUploadedFile("raft_s1.pdf", b"%PDF-1.4\nStudent 1 content\n%%EOF", content_type="application/pdf")
        sub_1 = submission_services.submit_file(asgn_1, pdf_1, self.student_1)
        submission_services.teacher_open_submission(sub_1, self.teacher)
        asgn_1.refresh_from_db()

        # Step 4: Student 2 progress updates & submits
        progress_services.add_progress_update(self.student_2, asgn_2, 75, "Leader election done.")
        pdf_2 = SimpleUploadedFile("raft_s2.pdf", b"%PDF-1.4\nStudent 2 content\n%%EOF", content_type="application/pdf")
        sub_2 = submission_services.submit_file(asgn_2, pdf_2, self.student_2)
        submission_services.teacher_open_submission(sub_2, self.teacher)
        asgn_2.refresh_from_db()

        # Step 5: Teacher grades Student 1 (90/100) -> Project still ASSIGNED
        reviews_services.assign_marks(asgn_1, self.teacher, 90.0, 100.0)
        project.refresh_from_db()
        self.assertEqual(project.status, ProjectStatus.ASSIGNED)

        # Step 6: Teacher grades Student 2 (80/100) -> All evaluated, Project becomes CLOSED
        reviews_services.assign_marks(asgn_2, self.teacher, 80.0, 100.0)
        project.refresh_from_db()
        self.assertEqual(project.status, ProjectStatus.CLOSED)

        # Step 7: Marks statistical report verification
        report = reviews_services.get_project_marks_report(project, self.teacher)
        self.assertEqual(len(report["records"]), 2)
        self.assertEqual(report["stats"]["evaluated_count"], 2)
        self.assertEqual(report["stats"]["average_percentage"], 85.0)
        self.assertEqual(report["stats"]["highest_percentage"], 90.0)
        self.assertEqual(report["stats"]["lowest_percentage"], 80.0)
