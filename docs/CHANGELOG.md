# Changelog

All notable changes to the Academic Project Management System (PMS) will be documented in this file.

## [Prompt 4] - Submissions App (UC10, UC11)
### Added
- Implemented `Submission` model in `submissions/models.py` (`assignment`, `file_path`, `file_name`, `file_size`, `version`, `submitted_on`, `is_late`, `formatted_size`, `extension`) with migrations. Files are stored on disk under `MEDIA_ROOT/uploads/<assignment_id>/` and metadata in the database.
- Implemented `submissions/services.py` containing complete business logic:
  - `submit_file()`: enforces assignment ownership, allowed submission states (`In progress`, `Overdue`, `Revision requested`, with automatic smooth progression from `Assigned`), non-empty check, `MAX_UPLOAD_SIZE` (10 MB), allowed extension check, magic bytes / file signature inspection (blocking `.exe`, `.dll`, PE, ELF, Mach-O binaries and disguised binaries), safe filename sanitization, version auto-increment (`previous_max + 1`), and atomic rollback removing orphaned disk files if database creation or transition fails.
  - Notification stub: `notify_teacher_new_submission()` invoked non-blockingly so notification failure never interrupts submission.
  - `teacher_open_submission()`: automatically transitions assignment from `Submitted` to `Under review` on teacher's initial inspection.
  - `get_submission_for_download()`: enforces strict authorization for downloads (students can only download their own deliverables, teachers only files from their supervised projects, 403/404 for unauthorized access).
- Implemented UC10 (Submit File): student file upload form on assignment detail view and dedicated upload page (`/submissions/upload/<assignment_id>/`), version history table, and late submission support for `Overdue` deliverables.
- Implemented UC11 (View Submissions): teacher submissions monitoring table (`/submissions/`) with project and status filters, student details, version tags, file sizes, timestamps, and "Late" vs "On Time" badges.
- Implemented secure streaming file downloads via `FileResponse(as_attachment=True)` with no public `/media/` serving in production.
- Added comprehensive test suite in `submissions/tests/test_submissions.py` using `override_settings(MEDIA_ROOT=tempdir)` covering all 13 required scenarios: valid PDF acceptance, `.exe` rejection, renamed `.exe` to `.pdf` rejected via signature check, oversize limit rejection, empty file rejection, path traversal filename sanitization, version incrementing on resubmission, atomic rollback with zero orphaned files or DB rows, unauthorized student rejection, automatic `Under review` state transition on teacher view, download permissions isolation, late submissions handling, and notification fault tolerance.

## [Prompt 3] - Progress Tracking App (UC07, UC08, UC09)
### Added
- Implemented `ProgressUpdate` model in `progress/models.py` with `assignment` foreign key, `percent_complete` (0-100 validator), `remarks`, and `updated_on` timestamp with migrations.
- Implemented `progress/services.py` with `add_progress_update()` enforcing non-decreasing percentage rules (0-100), ownership validation, locking after submission/evaluation, and state transitions (`Assigned` -> `In progress` on initial update; `Revision requested` -> `In progress`).
- Implemented UC07 (Update Progress): student milestone form integrated on assignment detail view and dedicated update page with dynamic Bootstrap progress bars and chronological history timelines.
- Implemented UC08 (Monitor Progress): teacher monitoring table with project and status filters, red highlighting for overdue assignments, amber alerting for stale updates (idle >= 7 days), and student history inspection.
- Implemented UC09 (Generate Progress Report): per-project report calculating average milestone completion and overdue counts, with print styling and CSV export.
- Connected real milestone progress updates to Sprint 2's project reports.
- Comprehensive test suite in `progress/tests/` covering validation boundaries, ownership security (404), status lockout, state machine triggers, teacher isolation, alert flags, and role protections (51 total tests passing with 90% overall code coverage).

## [Prompt 2] - Projects and Assignments Apps (UC03, UC04, UC05, UC06)
### Added
- Implemented `Project` model with `title`, `description`, `deadline`, `status` (`Draft`, `Assigned`, `Closed`), and `created_by` foreign key with migrations.
- Implemented `ProjectAssignment` model with `project`, `student`, `assigned_on`, `status` (`Assigned`, `In progress`, `Overdue`, `Submitted`, `Under review`, `Revision requested`, `Evaluated`), `unique_together` constraint, and `days_remaining` property.
- Implemented strict state machine transition services for `Project` (`transition()`) and `ProjectAssignment` (`transition()`), raising custom `InvalidTransition` on illegal transitions.
- Implemented UC03 (Create/Edit Project): teacher-only project creation and editing with future deadline validation, ownership checks (404 for other teachers' projects), status filtering, and pagination.
- Implemented UC04 (Assign Project): student selection with search by name/roll no, duplicate skipping, summary messaging ("N assigned, M already assigned"), automatic transition from `Draft` to `Assigned` on first assignment, and notification stub `notify_assignment()`.
- Implemented UC05 (View Assigned Project): student dashboard showing assigned projects, supervisor, deadline, status badge, days remaining, and strict 404 security checks preventing unauthorized viewing.
- Implemented UC06 (Generate Project Report): student evaluation summary table with print-friendly formatting and "Download CSV" export.
- Implemented `mark_overdue_assignments()` and management command `python manage.py mark_overdue` to transition past-deadline in-progress assignments to `Overdue`.
- Comprehensive test suites in `projects/tests/` and `assignments/tests/` verifying all 11 required behaviors (38 total tests passing with 90% overall code coverage).

## [Prompt 1] - Accounts App & Authentication (UC01 Register, UC02 Login)
### Added
- Implemented custom `User` model with `email` as `USERNAME_FIELD`, `name`, `role` (student/teacher), `department`, `roll_no` (students), `employee_id` (teachers), and lockout tracking (`failed_login_attempts`, `locked_until`).
- Implemented `accounts/services.py` containing all business rules: `register_user()`, `authenticate_user()` with 5-attempt brute-force protection (15-min lockout), `update_user_profile()`, and `change_user_password()`.
- Implemented role-based access decorators in `accounts/decorators.py`: `@teacher_required` and `@student_required` with login redirection for anonymous users and HTTP 403 for unauthorized roles.
- Created responsive registration page with dynamic vanilla JavaScript toggling roll number vs employee ID fields, login page, profile view/edit page, and change-password page.
- Created placeholder authenticated dashboard at `/dashboard/` displaying user welcome and role-specific action tiles.
- Added custom error templates: `templates/403.html`, `templates/404.html`, and `templates/500.html`.
- Added unit and integration test suite across `accounts/tests/` covering student/teacher registration, unique email validation, password strength validation, role requirements, brute-force lockout/mock-time unlock, POST-only logout, role decorators, and password hashing (24 passing tests).

## [Prompt 0] - Project Setup and Foundation
### Added
- Initialized Django 5 project `pms` and seven modular apps: `accounts`, `projects`, `assignments`, `progress`, `submissions`, `reviews`, `dashboard`.
- Structured each app with strict 4-layer architecture files: `models.py`, `forms.py`, `views.py`, `services.py`, `urls.py`, `tests/`, and `templates/<app>/`.
- Split Django configuration into `pms/settings/base.py`, `pms/settings/dev.py`, and `pms/settings/prod.py` powered by `python-decouple`.
- Configured custom user model `accounts.User` (`AUTH_USER_MODEL = "accounts.User"`), media/static file handling, upload constraints, and timezone `Asia/Kolkata`.
- Configured logging with console output and `logs/pms.log` rotating file handler.
- Created `templates/base.html` with responsive Bootstrap 5, role-aware navigation bar (anonymous, teacher, student), message alerts, and footer.
- Added `dashboard/home.html` landing page and smoke test in `dashboard/tests/test_smoke.py`.
- Added configuration templates (`.env.example`), `.gitignore`, `requirements.txt`, `requirements-dev.txt`, and documentation (`README.md`).
