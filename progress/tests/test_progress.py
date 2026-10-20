from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError
from accounts.models import UserRole
from accounts.services import register_user
from projects.services import create_project
from assignments.models import AssignmentStatus, ProjectAssignment
from assignments.services import assign_students_to_project, transition
from progress.models import ProgressUpdate
from progress.services import (
    add_progress_update, get_progress_summary,
    get_project_progress_report, generate_progress_csv_report
)


class ProgressTests(TestCase):
    def setUp(self):
        self.teacher_1 = register_user(
            name="Teacher One",
            email="teacher.one@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-01"
        )
        self.teacher_2 = register_user(
            name="Teacher Two",
            email="teacher.two@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-02"
        )
        self.student_1 = register_user(
            name="Student One",
            email="student.one@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="S-01"
        )
        self.student_2 = register_user(
            name="Student Two",
            email="student.two@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="S-02"
        )
        self.future_deadline = timezone.now() + timedelta(days=14)
        self.project_1 = create_project(
            teacher=self.teacher_1,
            title="Database Engine",
            description="Build storage engine",
            deadline=self.future_deadline
        )
        assign_students_to_project(self.teacher_1, self.project_1, [self.student_1.id])
        self.assignment_1 = ProjectAssignment.objects.get(project=self.project_1, student=self.student_1)

    def test_valid_progress_update_and_state_transition(self):
        """Valid update moves status from Assigned -> In progress on first update."""
        self.assertEqual(self.assignment_1.status, AssignmentStatus.ASSIGNED)

        update = add_progress_update(
            student=self.student_1,
            assignment=self.assignment_1,
            percent_complete=25,
            remarks="Completed initial schema and storage models."
        )
        self.assertEqual(update.percent_complete, 25)
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.IN_PROGRESS)

        # Subsequent valid update with higher percentage
        update_2 = add_progress_update(
            student=self.student_1,
            assignment=self.assignment_1,
            percent_complete=50,
            remarks="Indexed pages."
        )
        self.assertEqual(update_2.percent_complete, 50)
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.IN_PROGRESS)

    def test_below_previous_value_rejected(self):
        """Progress percentage cannot decrease below the latest recorded value."""
        add_progress_update(self.student_1, self.assignment_1, 40, "Initial 40%")

        with self.assertRaises(ValidationError) as ctx:
            add_progress_update(self.student_1, self.assignment_1, 35, "Lower percentage should fail")
        self.assertIn("percent_complete", ctx.exception.message_dict)

    def test_percent_bounds_rejected(self):
        """Values < 0 and > 100 are rejected."""
        with self.assertRaises(ValidationError) as ctx_neg:
            add_progress_update(self.student_1, self.assignment_1, -5)
        self.assertIn("percent_complete", ctx_neg.exception.message_dict)

        with self.assertRaises(ValidationError) as ctx_high:
            add_progress_update(self.student_1, self.assignment_1, 105)
        self.assertIn("percent_complete", ctx_high.exception.message_dict)

    def test_another_student_assignment_returns_404(self):
        """A student cannot submit progress on another student's assignment."""
        self.client.force_login(self.student_2)
        response = self.client.post(
            reverse('progress:update_progress', kwargs={'assignment_id': self.assignment_1.pk}),
            {'percent_complete': 30, 'remarks': 'Hacking update'}
        )
        self.assertEqual(response.status_code, 404)

    def test_blocked_after_submission(self):
        """Progress updates are rejected once assignment is Submitted, Under review, or Evaluated."""
        add_progress_update(self.student_1, self.assignment_1, 75, "Almost done")
        # Move to Submitted
        transition(self.assignment_1, AssignmentStatus.SUBMITTED)

        with self.assertRaises(ValidationError):
            add_progress_update(self.student_1, self.assignment_1, 80, "Should be blocked")

        # Move to Under review
        transition(self.assignment_1, AssignmentStatus.UNDER_REVIEW)
        with self.assertRaises(ValidationError):
            add_progress_update(self.student_1, self.assignment_1, 80, "Should be blocked")

        # Move to Evaluated
        transition(self.assignment_1, AssignmentStatus.EVALUATED)
        with self.assertRaises(ValidationError):
            add_progress_update(self.student_1, self.assignment_1, 100, "Should be blocked")

    def test_status_transition_after_revision_requested(self):
        """Update moves status from Revision requested -> In progress."""
        add_progress_update(self.student_1, self.assignment_1, 50, "Phase 1")
        transition(self.assignment_1, AssignmentStatus.SUBMITTED)
        transition(self.assignment_1, AssignmentStatus.UNDER_REVIEW)
        transition(self.assignment_1, AssignmentStatus.REVISION_REQUESTED)
        self.assertEqual(self.assignment_1.status, AssignmentStatus.REVISION_REQUESTED)

        # Student submits an update
        add_progress_update(self.student_1, self.assignment_1, 65, "Resumed after review")
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.status, AssignmentStatus.IN_PROGRESS)

    def test_teacher_sees_only_own_projects_progress(self):
        """Teacher A cannot see progress from Teacher B's projects."""
        project_2 = create_project(
            teacher=self.teacher_2,
            title="Teacher 2 Project",
            description="Other project",
            deadline=self.future_deadline
        )
        assign_students_to_project(self.teacher_2, project_2, [self.student_2.id])

        # Teacher 1 monitor view
        summary_t1 = get_progress_summary(self.teacher_1)
        project_ids_t1 = [item['project'].id for item in summary_t1]
        self.assertIn(self.project_1.id, project_ids_t1)
        self.assertNotIn(project_2.id, project_ids_t1)

    def test_overdue_and_amber_flags_computed_correctly(self):
        """Overdue and stale (amber > 7 days) flags are computed properly."""
        # Create an assignment assigned 10 days ago with no updates
        past_assigned_time = timezone.now() - timedelta(days=10)
        ProjectAssignment.objects.filter(pk=self.assignment_1.pk).update(assigned_on=past_assigned_time)
        self.assignment_1.refresh_from_db()

        summary = get_progress_summary(self.teacher_1, project_id=self.project_1.id)
        self.assertEqual(len(summary), 1)
        # Stale because no update for 10 days
        self.assertTrue(summary[0]['is_stale'])
        self.assertFalse(summary[0]['is_overdue'])

        # Now mark assignment as Overdue
        transition(self.assignment_1, AssignmentStatus.IN_PROGRESS)
        transition(self.assignment_1, AssignmentStatus.OVERDUE)
        summary_overdue = get_progress_summary(self.teacher_1, project_id=self.project_1.id)
        self.assertTrue(summary_overdue[0]['is_overdue'])

    def test_report_averages_and_csv_generation(self):
        """Progress report computes correct averages, overdue counts, and CSV content."""
        assign_students_to_project(self.teacher_1, self.project_1, [self.student_2.id])
        a2 = ProjectAssignment.objects.get(project=self.project_1, student=self.student_2)

        # Student 1 has 60%, Student 2 has 40%
        add_progress_update(self.student_1, self.assignment_1, 60)
        add_progress_update(self.student_2, a2, 40)

        report = get_project_progress_report(self.teacher_1, self.project_1.id)
        self.assertEqual(report['total_students'], 2)
        self.assertEqual(report['avg_completion'], 50.0)

        # CSV report
        csv_text = generate_progress_csv_report(self.teacher_1, self.project_1.id)
        self.assertIn("Student One", csv_text)
        self.assertIn("60%", csv_text)
        self.assertIn("Student Two", csv_text)
        self.assertIn("40%", csv_text)

    def test_student_cannot_access_monitor_or_report_returns_403(self):
        """Student cannot access teacher monitor or report views (403 Forbidden)."""
        self.client.force_login(self.student_1)

        monitor_resp = self.client.get(reverse('progress:monitor_progress'))
        self.assertEqual(monitor_resp.status_code, 403)

        report_resp = self.client.get(reverse('progress:progress_report', kwargs={'project_id': self.project_1.pk}))
        self.assertEqual(report_resp.status_code, 403)

    def test_student_progress_web_views(self):
        """Student can access update picker, update progress page, and submit progress."""
        self.client.force_login(self.student_1)

        # Picker view (single assignment redirects to update page)
        picker_resp = self.client.get(reverse('progress:student_progress_list'))
        self.assertEqual(picker_resp.status_code, 302)

        # Update page GET
        update_page_resp = self.client.get(
            reverse('progress:update_progress', kwargs={'assignment_id': self.assignment_1.pk})
        )
        self.assertEqual(update_page_resp.status_code, 200)
        self.assertContains(update_page_resp, "Current Progress")

        # Update page POST
        post_resp = self.client.post(
            reverse('progress:update_progress', kwargs={'assignment_id': self.assignment_1.pk}),
            {'percent_complete': 30, 'remarks': 'Initial 30 percent progress'}
        )
        self.assertRedirects(
            post_resp,
            reverse('progress:update_progress', kwargs={'assignment_id': self.assignment_1.pk})
        )
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.progress_updates.first().percent_complete, 30)

        # Update via assignment_detail POST
        detail_post_resp = self.client.post(
            reverse('assignments:assignment_detail', kwargs={'pk': self.assignment_1.pk}),
            {'update_progress': '1', 'percent_complete': 45, 'remarks': 'Pushed to 45%'}
        )
        self.assertRedirects(
            detail_post_resp,
            reverse('assignments:assignment_detail', kwargs={'pk': self.assignment_1.pk})
        )
        self.assignment_1.refresh_from_db()
        self.assertEqual(self.assignment_1.progress_updates.first().percent_complete, 45)

    def test_teacher_monitor_and_report_web_views(self):
        """Teacher can monitor progress, view student history, and export reports."""
        self.client.force_login(self.teacher_1)

        # Monitor progress view
        monitor_resp = self.client.get(reverse('progress:monitor_progress'))
        self.assertEqual(monitor_resp.status_code, 200)
        self.assertContains(monitor_resp, "Student One")

        # Student progress history view
        history_resp = self.client.get(
            reverse('progress:assignment_progress_history', kwargs={'assignment_id': self.assignment_1.pk})
        )
        self.assertEqual(history_resp.status_code, 200)
        self.assertContains(history_resp, "Student Milestone History")

        # Report select view
        report_select_resp = self.client.get(reverse('progress:progress_report_select'))
        self.assertEqual(report_select_resp.status_code, 200)
        self.assertContains(report_select_resp, self.project_1.title)

        # Project progress report HTML view
        report_resp = self.client.get(
            reverse('progress:progress_report', kwargs={'project_id': self.project_1.pk})
        )
        self.assertEqual(report_resp.status_code, 200)
        self.assertContains(report_resp, "Milestone Progress Report")

        # Project progress report CSV download
        csv_resp = self.client.get(
            reverse('progress:progress_report_csv', kwargs={'project_id': self.project_1.pk})
        )
        self.assertEqual(csv_resp.status_code, 200)
        self.assertEqual(csv_resp['Content-Type'], 'text/csv')
        self.assertIn('attachment;', csv_resp['Content-Disposition'])

