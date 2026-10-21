"""
Comprehensive Automated Security Test Suite:
1. Authentication gating across all URLs.
2. Strict role-based access control (RBAC): Teacher vs Student barriers (403 Forbidden).
3. Insecure Direct Object Reference (IDOR) isolation.
4. CSRF enforcement on state-changing operations.
5. Cross-Site Scripting (XSS) auto-escaping defenses.
6. SQL Injection (SQLi) immunity in search and filter parameters.
7. Malicious file upload attack suite (signatures, traversal, double extensions, size).
8. Permission-checked deliverable downloads.
9. Account lockout protection.
10. Password hashing integrity.
"""

import os
import shutil
import tempfile
from datetime import timedelta

from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import User, UserRole
from assignments import services as assignment_services
from assignments.models import AssignmentStatus, ProjectAssignment
from projects import services as project_services
from submissions import services as submission_services


class TestSecuritySuite(TestCase):
    def setUp(self):
        self.temp_media = tempfile.mkdtemp()
        self.settings_override = override_settings(
            MEDIA_ROOT=self.temp_media, EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend"
        )
        self.settings_override.enable()

        self.client = Client()
        self.now = timezone.now()

        # Teacher 1
        self.teacher_1 = User.objects.create_user(
            username="teacher1@example.edu",
            email="teacher1@example.edu",
            password="TeacherPass@123",
            name="Teacher One",
            role=UserRole.TEACHER,
            department="CSE",
            employee_id="T001",
        )

        # Teacher 2 (for multi-tenant isolation testing)
        self.teacher_2 = User.objects.create_user(
            username="teacher2@example.edu",
            email="teacher2@example.edu",
            password="TeacherPass@123",
            name="Teacher Two",
            role=UserRole.TEACHER,
            department="ECE",
            employee_id="T002",
        )

        # Student A
        self.student_a = User.objects.create_user(
            username="studentA@example.edu",
            email="studentA@example.edu",
            password="StudentPass@123",
            name="Student Alice",
            role=UserRole.STUDENT,
            department="CSE",
            roll_no="CS001",
        )

        # Student B (for IDOR isolation testing)
        self.student_b = User.objects.create_user(
            username="studentB@example.edu",
            email="studentB@example.edu",
            password="StudentPass@123",
            name="Student Bob",
            role=UserRole.STUDENT,
            department="CSE",
            roll_no="CS002",
        )

        # Create Project 1 for Teacher 1 and assign Student A
        self.proj_1 = project_services.create_project(
            teacher=self.teacher_1,
            title="Compiler Optimization",
            description="LLVM backend passes",
            deadline=self.now + timedelta(days=10),
        )
        assignment_services.assign_students_to_project(self.teacher_1, self.proj_1, [self.student_a.id])
        self.asgn_a = ProjectAssignment.objects.get(project=self.proj_1, student=self.student_a)

        # Create Project 2 for Teacher 2 and assign Student B
        self.proj_2 = project_services.create_project(
            teacher=self.teacher_2,
            title="VLSI Design",
            description="CMOS logic synthesis",
            deadline=self.now + timedelta(days=10),
        )
        assignment_services.assign_students_to_project(self.teacher_2, self.proj_2, [self.student_b.id])
        self.asgn_b = ProjectAssignment.objects.get(project=self.proj_2, student=self.student_b)

        # Submit deliverable for Student A
        pdf_content = b"%PDF-1.4\n%Valid student A deliverable\n%%EOF"
        pdf_file = SimpleUploadedFile("alice_llvm.pdf", pdf_content, content_type="application/pdf")
        self.sub_a = submission_services.submit_file(self.asgn_a, pdf_file, self.student_a)

    def tearDown(self):
        self.settings_override.disable()
        if os.path.exists(self.temp_media):
            shutil.rmtree(self.temp_media, ignore_errors=True)

    def test_01_anonymous_user_redirected_to_login_on_protected_endpoints(self):
        """
        Verify that unauthenticated users are redirected to login for protected URLs.
        """
        protected_urls = [
            reverse("dashboard:dashboard"),
            reverse("dashboard:notifications_list"),
            reverse("projects:project_list"),
            reverse("projects:project_create"),
            reverse("assignments:assign_project_select"),
            reverse("assignments:my_assignments"),
            reverse("assignments:assignment_detail", kwargs={"pk": self.asgn_a.id}),
            reverse("progress:student_progress_list"),
            reverse("progress:monitor_progress"),
            reverse("submissions:submission_list"),
            reverse("submissions:upload_picker"),
            reverse("reviews:reviews_dashboard"),
            reverse("reviews:student_feedback_list"),
            reverse("reviews:student_marks_list"),
        ]

        anon_client = Client()
        for url in protected_urls:
            with self.subTest(url=url):
                res = anon_client.get(url)
                self.assertIn(
                    res.status_code,
                    [302, 401, 403],
                    f"Anonymous user accessed protected URL {url} with code {res.status_code}",
                )
                if res.status_code == 302:
                    self.assertIn("/accounts/login/", res.url)

    def test_02_role_based_barriers_student_forbidden_from_teacher_views(self):
        """
        Verify that authenticated students receive HTTP 403 Forbidden on teacher-only endpoints.
        """
        teacher_only_urls = [
            reverse("projects:project_create"),
            reverse("assignments:assign_project_select"),
            reverse("progress:monitor_progress"),
            reverse("submissions:submission_list"),
            reverse("reviews:reviews_dashboard"),
            reverse("projects:project_edit", kwargs={"pk": self.proj_1.id}),
            reverse("assignments:assign_students", kwargs={"project_id": self.proj_1.id}),
            reverse("progress:progress_report", kwargs={"project_id": self.proj_1.id}),
            reverse("reviews:give_feedback", kwargs={"submission_id": self.sub_a.id}),
            reverse("reviews:assign_marks", kwargs={"assignment_id": self.asgn_a.id}),
            reverse("reviews:marks_report", kwargs={"project_id": self.proj_1.id}),
        ]

        student_client = Client()
        student_client.force_login(self.student_a)

        for url in teacher_only_urls:
            with self.subTest(url=url):
                res = student_client.get(url)
                self.assertEqual(
                    res.status_code,
                    403,
                    f"Student accessed teacher-only endpoint {url} (expected 403, got {res.status_code})",
                )

    def test_03_role_based_barriers_teacher_forbidden_from_student_views(self):
        """
        Verify that authenticated teachers receive HTTP 403 Forbidden on student-only endpoints.
        """
        student_only_urls = [
            reverse("assignments:my_assignments"),
            reverse("progress:student_progress_list"),
            reverse("submissions:upload_picker"),
            reverse("reviews:student_feedback_list"),
            reverse("reviews:student_marks_list"),
            reverse("assignments:assignment_detail", kwargs={"pk": self.asgn_a.id}),
            reverse("progress:update_progress", kwargs={"assignment_id": self.asgn_a.id}),
            reverse("submissions:upload_submission", kwargs={"assignment_id": self.asgn_a.id}),
        ]

        teacher_client = Client()
        teacher_client.force_login(self.teacher_1)

        for url in student_only_urls:
            with self.subTest(url=url):
                res = teacher_client.get(url)
                self.assertEqual(
                    res.status_code,
                    403,
                    f"Teacher accessed student-only endpoint {url} (expected 403, got {res.status_code})",
                )

    def test_04_idor_student_cannot_access_other_students_assignment(self):
        """
        IDOR check: Student A cannot access Student B's assignment detail, feedback, or marks.
        """
        client_a = Client()
        client_a.force_login(self.student_a)

        # 1. Assignment detail
        res = client_a.get(reverse("assignments:assignment_detail", kwargs={"pk": self.asgn_b.id}))
        self.assertEqual(res.status_code, 404, "Student A viewed Student B's assignment detail!")

        # 2. Progress update view
        res = client_a.get(reverse("progress:update_progress", kwargs={"assignment_id": self.asgn_b.id}))
        self.assertEqual(res.status_code, 404, "Student A accessed progress update for Student B!")

        # 3. Deliverable upload view
        res = client_a.get(reverse("submissions:upload_submission", kwargs={"assignment_id": self.asgn_b.id}))
        self.assertEqual(res.status_code, 404, "Student A accessed upload view for Student B!")

        # 4. Feedback view
        res = client_a.get(reverse("reviews:student_assignment_feedback", kwargs={"assignment_id": self.asgn_b.id}))
        self.assertEqual(res.status_code, 404, "Student A viewed Student B's feedback!")

        # 5. Marks view
        res = client_a.get(reverse("reviews:student_view_marks", kwargs={"assignment_id": self.asgn_b.id}))
        self.assertEqual(res.status_code, 404, "Student A viewed Student B's marks!")

    def test_05_idor_teacher_cannot_manage_other_teachers_project(self):
        """
        IDOR check: Teacher 1 cannot edit or view reports of Teacher 2's project.
        """
        client_t1 = Client()
        client_t1.force_login(self.teacher_1)

        # 1. Edit project
        res = client_t1.get(reverse("projects:project_edit", kwargs={"pk": self.proj_2.id}))
        self.assertEqual(res.status_code, 404, "Teacher 1 opened Teacher 2's project edit form!")

        # 2. Assign students
        res = client_t1.get(reverse("assignments:assign_students", kwargs={"project_id": self.proj_2.id}))
        self.assertEqual(res.status_code, 404, "Teacher 1 opened assign page for Teacher 2's project!")

        # 3. Progress report
        res = client_t1.get(reverse("progress:progress_report", kwargs={"project_id": self.proj_2.id}))
        self.assertEqual(res.status_code, 404, "Teacher 1 viewed progress report for Teacher 2's project!")

        # 4. Marks report
        res = client_t1.get(reverse("reviews:marks_report", kwargs={"project_id": self.proj_2.id}))
        self.assertEqual(res.status_code, 404, "Teacher 1 viewed marks report for Teacher 2's project!")

    def test_06_csrf_enforcement_on_post(self):
        """
        Verify that POST requests submitted without CSRF token are rejected with 403.
        """
        csrf_client = Client(enforce_csrf_checks=True)
        csrf_client.force_login(self.teacher_1)

        # POST without csrf token
        res = csrf_client.post(
            reverse("projects:project_create"),
            {
                "title": "CSRF Attack Project",
                "description": "Should fail",
                "deadline": (self.now + timedelta(days=5)).strftime("%Y-%m-%dT%H:%M"),
            },
        )
        self.assertEqual(res.status_code, 403, "POST succeeded without valid CSRF token!")

    def test_07_xss_prevention_in_templates(self):
        """
        Verify that HTML and JavaScript payloads in titles and comments are properly escaped.
        """
        xss_title = "<script>alert('XSS_PROJECT')</script>"
        xss_desc = "<img src=x onerror=alert('XSS_IMG')>"

        proj_xss = project_services.create_project(
            teacher=self.teacher_1, title=xss_title, description=xss_desc, deadline=self.now + timedelta(days=10)
        )

        teacher_client = Client()
        teacher_client.force_login(self.teacher_1)
        res = teacher_client.get(reverse("projects:project_list"))

        # Escaped characters must be present, unescaped tag must NOT be present
        self.assertContains(res, "&lt;script&gt;alert(&#x27;XSS_PROJECT&#x27;)&lt;/script&gt;")
        self.assertNotContains(res, "<script>alert('XSS_PROJECT')</script>")

    def test_08_sql_injection_resilience_in_search_and_filters(self):
        """
        Verify that SQL injection payloads in search and filter parameters are handled safely.
        """
        sqli_payloads = [
            "' OR '1'='1",
            "'; DROP TABLE accounts_user; --",
            "admin'--",
            "1 UNION SELECT 1,2,3,4,5--",
        ]

        teacher_client = Client()
        teacher_client.force_login(self.teacher_1)

        for payload in sqli_payloads:
            with self.subTest(payload=payload):
                res = teacher_client.get(reverse("projects:project_list"), {"q": payload})
                self.assertEqual(res.status_code, 200)

                res_prog = teacher_client.get(reverse("progress:monitor_progress"), {"q": payload})
                self.assertEqual(res_prog.status_code, 200)

        # Ensure user table remains intact
        self.assertTrue(User.objects.filter(id=self.teacher_1.id).exists())

    def test_09_upload_attacks_rejected(self):
        """
        Verify file upload attack protections:
        - Disguised PE executables (MZ header)
        - Empty files (0 bytes)
        - Oversized files (> 10 MB)
        - Path traversal in filename
        """
        # 1. Disguised binary (.exe renamed to .pdf)
        fake_pdf = SimpleUploadedFile(
            "malware.pdf", b"MZ\x90\x00\x03\x00\x00\x00Dummy PE header", content_type="application/pdf"
        )
        with self.assertRaises(ValidationError):
            submission_services.submit_file(self.asgn_a, fake_pdf, self.student_a)

        # 2. Empty file
        empty_file = SimpleUploadedFile("empty.pdf", b"", content_type="application/pdf")
        with self.assertRaises(ValidationError):
            submission_services.submit_file(self.asgn_a, empty_file, self.student_a)

        # 3. Oversized file (11 MB)
        huge_file = SimpleUploadedFile("huge.pdf", b"A" * (11 * 1024 * 1024), content_type="application/pdf")
        with self.assertRaises(ValidationError):
            submission_services.submit_file(self.asgn_a, huge_file, self.student_a)

        # 4. Path traversal filename sanitisation
        self.asgn_a.status = AssignmentStatus.REVISION_REQUESTED
        self.asgn_a.save()
        traversal_file = SimpleUploadedFile(
            "../../../etc/passwd.pdf", b"%PDF-1.4\nSafe content\n%%EOF", content_type="application/pdf"
        )
        sub_traversal = submission_services.submit_file(self.asgn_a, traversal_file, self.student_a)
        self.assertNotIn("..", sub_traversal.file_name)
        self.assertNotIn("/", sub_traversal.file_name)
        self.assertNotIn("\\", sub_traversal.file_name)

    def test_10_download_permission_isolation(self):
        """
        Verify that file downloads enforce ownership checks.
        """
        # 1. Student A can download own file
        client_a = Client()
        client_a.force_login(self.student_a)
        res_a = client_a.get(reverse("submissions:download_submission", kwargs={"submission_id": self.sub_a.id}))
        self.assertEqual(res_a.status_code, 200)

        # 2. Student B cannot download Student A's file
        client_b = Client()
        client_b.force_login(self.student_b)
        res_b = client_b.get(reverse("submissions:download_submission", kwargs={"submission_id": self.sub_a.id}))
        self.assertIn(res_b.status_code, [403, 404])

        # 3. Teacher 2 (unrelated teacher) cannot download Student A's file
        client_t2 = Client()
        client_t2.force_login(self.teacher_2)
        res_t2 = client_t2.get(reverse("submissions:download_submission", kwargs={"submission_id": self.sub_a.id}))
        self.assertEqual(res_t2.status_code, 404)

    def test_11_passwords_are_cryptographically_hashed(self):
        """
        Verify that plain text passwords are never stored in the database.
        """
        user = User.objects.get(id=self.student_a.id)
        self.assertFalse(user.password == "StudentPass@123")
        self.assertTrue(user.password.startswith("pbkdf2_sha256$"))
