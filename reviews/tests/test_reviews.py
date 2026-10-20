import os
import shutil
import tempfile
from decimal import Decimal
from datetime import timedelta
from unittest.mock import patch

from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.exceptions import ValidationError, PermissionDenied
from django.urls import reverse
from django.utils import timezone
from django.http import Http404

from accounts.models import UserRole
from accounts.services import register_user
from projects.models import Project, ProjectStatus
from projects.services import create_project
from assignments.models import AssignmentStatus, ProjectAssignment
from assignments.services import assign_students_to_project, transition
from progress.services import add_progress_update
from submissions.services import submit_file, teacher_open_submission
from reviews.models import Feedback, Marks
from reviews.services import (
    give_feedback, assign_marks, get_student_feedbacks,
    get_student_marks, get_project_marks_report, generate_marks_csv
)


class ReviewsTests(TestCase):
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
            email="teacher1@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-01"
        )
        self.teacher_2 = register_user(
            name="Teacher Two",
            email="teacher2@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-02"
        )
        self.student_1 = register_user(
            name="Alice Student",
            email="alice@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="CS-01"
        )
        self.student_2 = register_user(
            name="Bob Student",
            email="bob@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="CS-02"
        )

        self.deadline = timezone.now() + timedelta(days=14)
        self.project = create_project(
            teacher=self.teacher_1,
            title="Compiler Optimization",
            description="LLVM backend passes",
            deadline=self.deadline
        )
        assign_students_to_project(self.teacher_1, self.project, [self.student_1.id])
        self.assignment_1 = ProjectAssignment.objects.get(project=self.project, student=self.student_1)

    def _create_submission(self, assignment, student, filename="code.pdf"):
        with override_settings(MEDIA_ROOT=self.temp_media):
            pdf_bytes = b"%PDF-1.4\ncontent\n%%EOF"
            upload = SimpleUploadedFile(filename, pdf_bytes, content_type="application/pdf")
            return submit_file(assignment, upload, student)

    def test_feedback_only_on_own_projects(self):
        """Teacher can only give feedback on submissions for their own projects."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        # Teacher 1 opens submission -> Under review
        teacher_open_submission(sub, self.teacher_1)

        # Teacher 2 tries to give feedback -> Http404
        with self.assertRaises(Http404):
            give_feedback(sub, self.teacher_2, "Good work", request_revision=False)

    def test_revision_flag_changes_state(self):
        """Request revision flag moves assignment Under review -> Revision requested; False keeps it Under review."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)

        # 1. False -> stays Under review
        fb1 = give_feedback(sub, self.teacher_1, "Looking decent.", request_revision=False)
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.UNDER_REVIEW)
        self.assertFalse(fb1.requested_revision)

        # 2. True -> moves to Revision requested
        fb2 = give_feedback(sub, self.teacher_1, "Needs major fixes.", request_revision=True)
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.REVISION_REQUESTED)
        self.assertTrue(fb2.requested_revision)

    def test_student_cannot_post_feedback_403(self):
        """Student attempting to post feedback gets 403 Forbidden."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        self.client.force_login(self.student_1)

        url = reverse('reviews:give_feedback', kwargs={'submission_id': sub.id})
        response = self.client.post(url, {'comments': 'Hacked feedback', 'requested_revision': False})
        self.assertEqual(response.status_code, 403)

    def test_marks_rejected_without_a_submission(self):
        """Assigning marks fails if the assignment has no submitted deliverables."""
        # assignment_1 has no submissions yet, transition to Under review is not even normal, but test rule directly
        with self.assertRaises(ValidationError) as ctx:
            assign_marks(self.assignment_1, self.teacher_1, score=85, max_score=100)
        self.assertIn("at least one submitted deliverable", str(ctx.exception))

    def test_score_greater_than_max_and_negative_rejected(self):
        """Negative score or score exceeding max_score is rejected."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)

        # 1. Negative score
        with self.assertRaises(ValidationError) as ctx:
            assign_marks(self.assignment_1, self.teacher_1, score=-10, max_score=100)
        self.assertIn("score", ctx.exception.message_dict)

        # 2. Score > Max
        with self.assertRaises(ValidationError) as ctx:
            assign_marks(self.assignment_1, self.teacher_1, score=110, max_score=100)
        self.assertIn("score", ctx.exception.message_dict)

    def test_second_marks_row_blocked_and_updated_instead(self):
        """A second marks assignment updates existing row; only one Marks row exists per assignment."""
        # Assign second student so project remains open while student 1's marks are edited
        assign_students_to_project(self.teacher_1, self.project, [self.student_2.id])
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)

        # Initial grading
        m1 = assign_marks(self.assignment_1, self.teacher_1, score=75, max_score=100)
        self.assertEqual(Marks.objects.filter(assignment=self.assignment_1).count(), 1)
        self.assertEqual(m1.score, Decimal('75.00'))

        # Update marks
        m2 = assign_marks(self.assignment_1, self.teacher_1, score=90, max_score=100)
        self.assertEqual(Marks.objects.filter(assignment=self.assignment_1).count(), 1)
        self.assertEqual(m2.id, m1.id)
        self.assertEqual(m2.score, Decimal('90.00'))

    def test_all_assignments_evaluated_closes_the_project(self):
        """Project transitions to Closed only when ALL assigned students have been evaluated."""
        # Assign second student to same project
        assign_students_to_project(self.teacher_1, self.project, [self.student_2.id])
        assignment_2 = ProjectAssignment.objects.get(project=self.project, student=self.student_2)

        # Student 1 submits & is graded
        sub1 = self._create_submission(self.assignment_1, self.student_1, "sub1.pdf")
        teacher_open_submission(sub1, self.teacher_1)
        assign_marks(self.assignment_1, self.teacher_1, score=85, max_score=100)

        self.assignment_1.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.EVALUATED)
        # Project is still Assigned because student 2 is not evaluated
        self.assertEqual(self.project.status, ProjectStatus.ASSIGNED)

        # Student 2 submits & is graded
        sub2 = self._create_submission(assignment_2, self.student_2, "sub2.pdf")
        teacher_open_submission(sub2, self.teacher_1)
        assign_marks(assignment_2, self.teacher_1, score=92, max_score=100)

        assignment_2.refresh_from_db()
        self.project.refresh_from_db()
        self.assertEqual(assignment_2.status, AssignmentStatus.EVALUATED)
        # Now all assignments evaluated -> Project moves to Closed!
        self.assertEqual(self.project.status, ProjectStatus.CLOSED)

    def test_student_cannot_see_another_students_feedback_or_marks(self):
        """Students are strictly forbidden from viewing another student's feedback or marks."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)
        give_feedback(sub, self.teacher_1, "Alice's Private Feedback")
        assign_marks(self.assignment_1, self.teacher_1, score=88, max_score=100)

        # Student 2 tries to access Student 1's feedback
        with self.assertRaises(Http404):
            get_student_feedbacks(self.student_2, assignment_id=self.assignment_1.id)

        # Student 2 tries to access Student 1's marks
        with self.assertRaises(Http404):
            get_student_marks(self.student_2, assignment_id=self.assignment_1.id)

        # Web view permission check
        self.client.force_login(self.student_2)
        resp_fb = self.client.get(reverse('reviews:student_assignment_feedback', kwargs={'assignment_id': self.assignment_1.id}))
        self.assertEqual(resp_fb.status_code, 404)

        resp_marks = self.client.get(reverse('reviews:student_view_marks', kwargs={'assignment_id': self.assignment_1.id}))
        self.assertEqual(resp_marks.status_code, 404)

    def test_marks_hidden_before_evaluated(self):
        """Marks cannot be viewed by student before status is Evaluated."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)

        # Not yet evaluated
        with self.assertRaises(Http404):
            get_student_marks(self.student_1, assignment_id=self.assignment_1.id)

        self.client.force_login(self.student_1)
        resp = self.client.get(reverse('reviews:student_view_marks', kwargs={'assignment_id': self.assignment_1.id}))
        self.assertEqual(resp.status_code, 404)

    def test_report_statistics_correct(self):
        """Project marks report calculates correct average, highest, lowest, and pass/fail counts."""
        assign_students_to_project(self.teacher_1, self.project, [self.student_2.id])
        assignment_2 = ProjectAssignment.objects.get(project=self.project, student=self.student_2)

        # Student 1 gets 35% (Fail)
        sub1 = self._create_submission(self.assignment_1, self.student_1, "sub1.pdf")
        teacher_open_submission(sub1, self.teacher_1)
        assign_marks(self.assignment_1, self.teacher_1, score=35, max_score=100)

        # Student 2 gets 85% (Pass)
        sub2 = self._create_submission(assignment_2, self.student_2, "sub2.pdf")
        teacher_open_submission(sub2, self.teacher_1)
        assign_marks(assignment_2, self.teacher_1, score=85, max_score=100)

        report = get_project_marks_report(self.project, self.teacher_1)
        stats = report['stats']

        self.assertEqual(stats['total_students'], 2)
        self.assertEqual(stats['evaluated_count'], 2)
        self.assertEqual(stats['average_percentage'], 60.0)
        self.assertEqual(stats['highest_percentage'], 85.0)
        self.assertEqual(stats['lowest_percentage'], 35.0)
        self.assertEqual(stats['passing_count'], 1)
        self.assertEqual(stats['failing_count'], 1)

    def test_csv_export_content(self):
        """CSV export contains expected headers, student rows, and summary statistics."""
        sub1 = self._create_submission(self.assignment_1, self.student_1, "sub1.pdf")
        teacher_open_submission(sub1, self.teacher_1)
        assign_marks(self.assignment_1, self.teacher_1, score=95, max_score=100)

        csv_text = generate_marks_csv(self.project, self.teacher_1)
        self.assertIn("Academic Project Management System - Marks Report", csv_text)
        self.assertIn("Compiler Optimization", csv_text)
        self.assertIn("Alice Student", csv_text)
        self.assertIn("95.00", csv_text)
        self.assertIn("95.0%", csv_text)
        self.assertIn("PASS", csv_text)
        self.assertIn("Average Percentage", csv_text)

    def test_editing_marks_blocked_when_project_closed(self):
        """Editing marks is forbidden once the project has been Closed."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)
        # Grading the only student closes the project
        assign_marks(self.assignment_1, self.teacher_1, score=80, max_score=100)
        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.CLOSED)

        # Attempt to edit marks
        with self.assertRaises(ValidationError) as ctx:
            assign_marks(self.assignment_1, self.teacher_1, score=90, max_score=100)
        self.assertIn("project is closed", str(ctx.exception))

    def test_notification_failure_does_not_break_review_or_marks(self):
        """Notification exceptions do not prevent feedback or marks from being persisted."""
        sub = self._create_submission(self.assignment_1, self.student_1)
        teacher_open_submission(sub, self.teacher_1)

        # Feedback notification fail
        with patch('reviews.services.notify_student_new_feedback', side_effect=RuntimeError("Email Offline")):
            fb = give_feedback(sub, self.teacher_1, "Robust test feedback")
            self.assertIsNotNone(fb.id)

        # Marks notification fail
        with patch('reviews.services.notify_student_marks_assigned', side_effect=RuntimeError("Email Offline")):
            marks = assign_marks(self.assignment_1, self.teacher_1, score=88, max_score=100)
            self.assertIsNotNone(marks.id)

    def test_end_to_end_workflow(self):
        """
        End-to-End Master Workflow:
        create project -> assign -> progress -> submit -> feedback with revision ->
        resume -> resubmit -> marks -> project Closed.
        """
        with override_settings(MEDIA_ROOT=self.temp_media):
            # 1. Create project
            proj = create_project(
                teacher=self.teacher_1,
                title="Distributed KV Store",
                description="Raft-based store",
                deadline=timezone.now() + timedelta(days=20)
            )
            self.assertEqual(proj.status, ProjectStatus.DRAFT)

            # 2. Assign student (Draft -> Assigned)
            assign_students_to_project(self.teacher_1, proj, [self.student_1.id])
            proj.refresh_from_db()
            self.assertEqual(proj.status, ProjectStatus.ASSIGNED)
            assign = ProjectAssignment.objects.get(project=proj, student=self.student_1)
            self.assertEqual(assign.status, AssignmentStatus.ASSIGNED)

            # 3. Student updates progress (Assigned -> In progress)
            add_progress_update(self.student_1, assign, percent_complete=30, remarks="Design finished")
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.IN_PROGRESS)

            # 4. Student submits file (In progress -> Submitted)
            pdf_bytes = b"%PDF-1.4\nInitial draft\n%%EOF"
            upload_v1 = SimpleUploadedFile("draft_v1.pdf", pdf_bytes, content_type="application/pdf")
            sub_v1 = submit_file(assign, upload_v1, self.student_1)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.SUBMITTED)
            self.assertEqual(sub_v1.version, 1)

            # 5. Teacher opens submission (Submitted -> Under review)
            teacher_open_submission(sub_v1, self.teacher_1)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.UNDER_REVIEW)

            # 6. Teacher gives feedback with revision requested (Under review -> Revision requested)
            give_feedback(sub_v1, self.teacher_1, "Missing Raft heartbeat tests.", request_revision=True)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.REVISION_REQUESTED)

            # 7. Student resumes progress (Revision requested -> In progress)
            add_progress_update(self.student_1, assign, percent_complete=80, remarks="Added heartbeat and leader election")
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.IN_PROGRESS)

            # 8. Student resubmits file (In progress -> Submitted, version 2)
            pdf_bytes_v2 = b"%PDF-1.4\nFinal revised implementation\n%%EOF"
            upload_v2 = SimpleUploadedFile("final_v2.pdf", pdf_bytes_v2, content_type="application/pdf")
            sub_v2 = submit_file(assign, upload_v2, self.student_1)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.SUBMITTED)
            self.assertEqual(sub_v2.version, 2)

            # Teacher opens v2
            teacher_open_submission(sub_v2, self.teacher_1)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.UNDER_REVIEW)

            # 9. Teacher assigns marks (Under review -> Evaluated)
            marks = assign_marks(assign, self.teacher_1, score=92, max_score=100)
            assign.refresh_from_db()
            self.assertEqual(assign.status, AssignmentStatus.EVALUATED)
            self.assertEqual(marks.percentage, 92.0)
            self.assertEqual(marks.grade_band, 'A')
            self.assertTrue(marks.is_pass)

            # 10. Project transitions to Closed
            proj.refresh_from_db()
            self.assertEqual(proj.status, ProjectStatus.CLOSED)
