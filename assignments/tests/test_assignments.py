from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserRole
from accounts.services import register_user
from assignments.models import AssignmentStatus, ProjectAssignment
from assignments.services import (
    InvalidTransition,
    assign_students_to_project,
    mark_overdue_assignments,
    transition,
)
from projects.models import Project, ProjectStatus
from projects.services import create_project


class AssignmentTests(TestCase):
    def setUp(self):
        self.teacher = register_user(
            name="Teacher Diana",
            email="diana@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-009",
        )
        self.student_1 = register_user(
            name="Student Alex",
            email="alex@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="ALEX-01",
        )
        self.student_2 = register_user(
            name="Student Brian",
            email="brian@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="BRIAN-02",
        )
        self.student_3 = register_user(
            name="Student Clara",
            email="clara@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="CLARA-03",
        )
        self.future_deadline = timezone.now() + timedelta(days=10)
        self.project = create_project(
            teacher=self.teacher,
            title="Cloud Storage Architecture",
            description="Build S3 clone",
            deadline=self.future_deadline,
        )

    def test_assign_to_many_students_and_first_assignment_flips_draft_to_assigned(self):
        """Assigning students to a Draft project flips it to Assigned."""
        self.assertEqual(self.project.status, ProjectStatus.DRAFT)

        assigned, skipped = assign_students_to_project(
            teacher=self.teacher, project=self.project, student_ids=[self.student_1.id, self.student_2.id]
        )
        self.assertEqual(assigned, 2)
        self.assertEqual(skipped, 0)

        self.project.refresh_from_db()
        self.assertEqual(self.project.status, ProjectStatus.ASSIGNED)
        self.assertEqual(ProjectAssignment.objects.filter(project=self.project).count(), 2)

    def test_duplicate_assignment_skipped(self):
        """Already assigned students are skipped on subsequent assignment calls."""
        # Initial assignment
        assign_students_to_project(teacher=self.teacher, project=self.project, student_ids=[self.student_1.id])

        # Re-assign student 1 along with new student 2 and student 3
        assigned, skipped = assign_students_to_project(
            teacher=self.teacher,
            project=self.project,
            student_ids=[self.student_1.id, self.student_2.id, self.student_3.id],
        )
        self.assertEqual(assigned, 2)
        self.assertEqual(skipped, 1)
        self.assertEqual(ProjectAssignment.objects.filter(project=self.project).count(), 3)

    def test_student_sees_only_own_assignments_and_cannot_open_others_404(self):
        """Student sees only their own assignments; opening another student's assignment returns 404."""
        assign_students_to_project(
            teacher=self.teacher, project=self.project, student_ids=[self.student_1.id, self.student_2.id]
        )

        assignment_1 = ProjectAssignment.objects.get(project=self.project, student=self.student_1)
        assignment_2 = ProjectAssignment.objects.get(project=self.project, student=self.student_2)

        # Student 1 logs in
        self.client.force_login(self.student_1)
        list_response = self.client.get(reverse("assignments:my_assignments"))
        self.assertEqual(list_response.status_code, 200)
        self.assertContains(list_response, self.project.title)

        # Student 1 opens their own assignment -> 200 OK
        own_detail = self.client.get(reverse("assignments:assignment_detail", kwargs={"pk": assignment_1.pk}))
        self.assertEqual(own_detail.status_code, 200)

        # Student 1 opens Student 2's assignment -> 404 Not Found
        other_detail = self.client.get(reverse("assignments:assignment_detail", kwargs={"pk": assignment_2.pk}))
        self.assertEqual(other_detail.status_code, 404)

    def test_student_cannot_access_assign_view_returns_403(self):
        """Student cannot access teacher assignment view (403 Forbidden)."""
        self.client.force_login(self.student_1)
        response = self.client.get(reverse("assignments:assign_students", kwargs={"project_id": self.project.pk}))
        self.assertEqual(response.status_code, 403)

    def test_illegal_assignment_transition_raises_invalid_transition(self):
        """Illegal status transitions on ProjectAssignment raise InvalidTransition."""
        assign_students_to_project(teacher=self.teacher, project=self.project, student_ids=[self.student_1.id])
        assignment = ProjectAssignment.objects.get(project=self.project, student=self.student_1)
        self.assertEqual(assignment.status, AssignmentStatus.ASSIGNED)

        # Assigned cannot jump directly to Evaluated or Submitted
        with self.assertRaises(InvalidTransition):
            transition(assignment, AssignmentStatus.EVALUATED)

        with self.assertRaises(InvalidTransition):
            transition(assignment, AssignmentStatus.SUBMITTED)

        # Valid transition: Assigned -> In progress
        transition(assignment, AssignmentStatus.IN_PROGRESS)
        self.assertEqual(assignment.status, AssignmentStatus.IN_PROGRESS)

        # Valid transition: In progress -> Submitted
        transition(assignment, AssignmentStatus.SUBMITTED)
        self.assertEqual(assignment.status, AssignmentStatus.SUBMITTED)

        # Valid transition: Submitted -> Under review
        transition(assignment, AssignmentStatus.UNDER_REVIEW)
        self.assertEqual(assignment.status, AssignmentStatus.UNDER_REVIEW)

        # Valid transition: Under review -> Revision requested
        transition(assignment, AssignmentStatus.REVISION_REQUESTED)
        self.assertEqual(assignment.status, AssignmentStatus.REVISION_REQUESTED)

        # Valid transition: Revision requested -> In progress
        transition(assignment, AssignmentStatus.IN_PROGRESS)
        self.assertEqual(assignment.status, AssignmentStatus.IN_PROGRESS)

        # In progress -> Submitted -> Under review -> Evaluated
        transition(assignment, AssignmentStatus.SUBMITTED)
        transition(assignment, AssignmentStatus.UNDER_REVIEW)
        transition(assignment, AssignmentStatus.EVALUATED)
        self.assertEqual(assignment.status, AssignmentStatus.EVALUATED)

        # Evaluated is final: cannot transition anywhere
        with self.assertRaises(InvalidTransition):
            transition(assignment, AssignmentStatus.IN_PROGRESS)

    def test_mark_overdue_command_affects_only_in_progress_past_deadline(self):
        """
        Overdue command only marks assignments that are 'In progress' with a passed deadline.
        Assignments still in 'Assigned', already 'Submitted', or before deadline are unaffected.
        """
        # Project 1: Deadline is in the past
        past_project = create_project(
            teacher=self.teacher,
            title="Past Due Project",
            description="Should be checked",
            deadline=timezone.now() + timedelta(days=1),  # temporarily future to create
        )
        # Update deadline directly in DB to simulate past
        past_time = timezone.now() - timedelta(days=2)
        Project.objects.filter(pk=past_project.pk).update(deadline=past_time)
        past_project.refresh_from_db()

        # Assignment 1: In progress with past deadline -> SHOULD become Overdue
        assign_students_to_project(self.teacher, past_project, [self.student_1.id])
        a1 = ProjectAssignment.objects.get(project=past_project, student=self.student_1)
        transition(a1, AssignmentStatus.IN_PROGRESS)

        # Assignment 2: Still 'Assigned' (student hasn't started yet) -> NOT overdue
        assign_students_to_project(self.teacher, past_project, [self.student_2.id])
        a2 = ProjectAssignment.objects.get(project=past_project, student=self.student_2)

        # Assignment 3: Future deadline 'In progress' -> NOT overdue
        assign_students_to_project(self.teacher, self.project, [self.student_3.id])
        a3 = ProjectAssignment.objects.get(project=self.project, student=self.student_3)
        transition(a3, AssignmentStatus.IN_PROGRESS)

        # Run mark_overdue command
        marked_count = mark_overdue_assignments()
        self.assertEqual(marked_count, 1)

        a1.refresh_from_db()
        a2.refresh_from_db()
        a3.refresh_from_db()

        self.assertEqual(a1.status, AssignmentStatus.OVERDUE)
        self.assertEqual(a2.status, AssignmentStatus.ASSIGNED)
        self.assertEqual(a3.status, AssignmentStatus.IN_PROGRESS)

        # Also test management command invocation
        call_command("mark_overdue")

    def test_assign_views(self):
        """Teacher can open assign selection page and submit assignments via web form."""
        self.client.force_login(self.teacher)

        # Select view
        select_resp = self.client.get(reverse("assignments:assign_project_select"))
        self.assertEqual(select_resp.status_code, 200)
        self.assertContains(select_resp, self.project.title)

        # Assign students GET view with search
        assign_get = self.client.get(
            reverse("assignments:assign_students", kwargs={"project_id": self.project.pk}) + "?q=Alex"
        )
        self.assertEqual(assign_get.status_code, 200)
        self.assertContains(assign_get, "Student Alex")

        # Assign students POST view
        assign_post = self.client.post(
            reverse("assignments:assign_students", kwargs={"project_id": self.project.pk}),
            {"student_ids": [str(self.student_1.id), str(self.student_2.id)]},
        )
        self.assertRedirects(assign_post, reverse("projects:project_detail", kwargs={"pk": self.project.pk}))
        self.assertEqual(ProjectAssignment.objects.filter(project=self.project).count(), 2)
