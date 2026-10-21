from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserRole
from accounts.services import register_user
from projects.models import Project, ProjectStatus
from projects.services import (
    InvalidTransition,
    create_project,
    generate_project_csv_report,
    transition,
    update_project,
)


class ProjectTests(TestCase):
    def setUp(self):
        self.teacher_a = register_user(
            name="Teacher Alice",
            email="teacher.a@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-001",
        )
        self.teacher_b = register_user(
            name="Teacher Bob",
            email="teacher.b@example.edu",
            password="StrongPassword#2024",
            role=UserRole.TEACHER,
            employee_id="T-002",
        )
        self.student = register_user(
            name="Student Sam",
            email="student.sam@example.edu",
            password="StrongPassword#2024",
            role=UserRole.STUDENT,
            roll_no="S-001",
        )
        self.future_deadline = timezone.now() + timedelta(days=14)

    def test_teacher_creates_and_edits_project(self):
        """Teacher can create a project in Draft status and edit it."""
        project = create_project(
            teacher=self.teacher_a,
            title="Machine Learning Classifier",
            description="Build a robust classifier.",
            deadline=self.future_deadline,
        )
        self.assertEqual(project.status, ProjectStatus.DRAFT)
        self.assertEqual(project.created_by, self.teacher_a)

        # Edit project
        new_deadline = timezone.now() + timedelta(days=21)
        updated = update_project(
            project=project,
            teacher=self.teacher_a,
            title="Updated ML Classifier",
            description="Updated objectives and datasets.",
            deadline=new_deadline,
        )
        self.assertEqual(updated.title, "Updated ML Classifier")
        self.assertEqual(updated.deadline, new_deadline)

    def test_past_deadline_rejected_on_creation(self):
        """Creating a project with a past deadline raises ValidationError."""
        past_deadline = timezone.now() - timedelta(days=1)
        with self.assertRaises(ValidationError) as ctx:
            create_project(
                teacher=self.teacher_a, title="Past Project", description="Should fail", deadline=past_deadline
            )
        self.assertIn("deadline", ctx.exception.message_dict)

    def test_teacher_a_cannot_edit_teacher_b_project_returns_404(self):
        """Teacher A attempting to edit Teacher B's project receives 404."""
        project_b = create_project(
            teacher=self.teacher_b,
            title="Bob's Cryptography Project",
            description="Quantum crypto",
            deadline=self.future_deadline,
        )
        self.client.force_login(self.teacher_a)
        response = self.client.get(reverse("projects:project_edit", kwargs={"pk": project_b.pk}))
        self.assertEqual(response.status_code, 404)

        # POST also returns 404
        post_response = self.client.post(
            reverse("projects:project_edit", kwargs={"pk": project_b.pk}),
            {
                "title": "Hacked Title",
                "description": "Hacked",
                "deadline": self.future_deadline.strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(post_response.status_code, 404)

    def test_student_cannot_access_project_create_or_edit_returns_403(self):
        """Student attempting to create or edit projects is denied with 403."""
        project = create_project(
            teacher=self.teacher_a,
            title="Operating Systems Kernel",
            description="Kernel design",
            deadline=self.future_deadline,
        )
        self.client.force_login(self.student)

        create_response = self.client.get(reverse("projects:project_create"))
        self.assertEqual(create_response.status_code, 403)

        edit_response = self.client.get(reverse("projects:project_edit", kwargs={"pk": project.pk}))
        self.assertEqual(edit_response.status_code, 403)

    def test_illegal_project_transition_raises_invalid_transition(self):
        """Project cannot jump directly from Draft to Closed or Closed to Draft."""
        project = create_project(
            teacher=self.teacher_a,
            title="Compiler Design",
            description="Lexing & parsing",
            deadline=self.future_deadline,
        )
        # Draft -> Closed is illegal (must be Draft -> Assigned -> Closed)
        with self.assertRaises(InvalidTransition):
            transition(project, ProjectStatus.CLOSED)

        # Legal: Draft -> Assigned
        transition(project, ProjectStatus.ASSIGNED)
        self.assertEqual(project.status, ProjectStatus.ASSIGNED)

        # Legal: Assigned -> Closed
        transition(project, ProjectStatus.CLOSED)
        self.assertEqual(project.status, ProjectStatus.CLOSED)

        # Closed -> Draft is illegal
        with self.assertRaises(InvalidTransition):
            transition(project, ProjectStatus.DRAFT)

    def test_csv_report_content_correct(self):
        """Project CSV report generates proper headers and student assignment rows."""
        project = create_project(
            teacher=self.teacher_a,
            title="Database Internals",
            description="B-Tree indexing",
            deadline=self.future_deadline,
        )
        self.client.force_login(self.teacher_a)

        # CSV report when empty
        csv_text = generate_project_csv_report(project, self.teacher_a)
        self.assertIn("Student Name,Roll Number,Email,Department,Assignment Status", csv_text)

        # Download via view
        response = self.client.get(reverse("projects:project_report_csv", kwargs={"pk": project.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "text/csv")
        self.assertIn(f'attachment; filename="project_{project.id}_report.csv"', response["Content-Disposition"])

    def test_project_list_and_detail_views(self):
        """Teacher can view project list, apply status filter, and view detail."""
        project = create_project(
            teacher=self.teacher_a,
            title="Distributed Consensus",
            description="Paxos and Raft",
            deadline=self.future_deadline,
        )
        self.client.force_login(self.teacher_a)

        # List view
        list_resp = self.client.get(reverse("projects:project_list"))
        self.assertEqual(list_resp.status_code, 200)
        self.assertContains(list_resp, "Distributed Consensus")

        # Filter by status
        filter_resp = self.client.get(reverse("projects:project_list") + "?status=Draft")
        self.assertEqual(filter_resp.status_code, 200)
        self.assertContains(filter_resp, "Distributed Consensus")

        # Detail view
        detail_resp = self.client.get(reverse("projects:project_detail", kwargs={"pk": project.pk}))
        self.assertEqual(detail_resp.status_code, 200)
        self.assertContains(detail_resp, "Paxos and Raft")

        # Report HTML view
        report_resp = self.client.get(reverse("projects:project_report", kwargs={"pk": project.pk}))
        self.assertEqual(report_resp.status_code, 200)
        self.assertContains(report_resp, "Project Monitoring Report")

    def test_project_create_and_edit_via_web_form(self):
        """Teacher can create and edit projects through web forms."""
        self.client.force_login(self.teacher_a)

        # Create POST
        deadline_str = self.future_deadline.strftime("%Y-%m-%dT%H:%M")
        create_resp = self.client.post(
            reverse("projects:project_create"),
            {"title": "Web Form Project", "description": "Created via web form", "deadline": deadline_str},
        )
        self.assertRedirects(create_resp, reverse("projects:project_list"))
        created = Project.objects.get(title="Web Form Project")
        self.assertEqual(created.created_by, self.teacher_a)

        # Edit POST
        edit_resp = self.client.post(
            reverse("projects:project_edit", kwargs={"pk": created.pk}),
            {"title": "Web Form Project (Edited)", "description": "Updated via web form", "deadline": deadline_str},
        )
        self.assertRedirects(edit_resp, reverse("projects:project_list"))
        created.refresh_from_db()
        self.assertEqual(created.title, "Web Form Project (Edited)")
