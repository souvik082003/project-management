# Academic Project Management System (PMS) - Test Plan

## Overview
This document specifies the comprehensive test plan for the Web-Based Project Management System for Academic Project Monitoring and Evaluation (PMS). It covers all 17 system use cases (UC01–UC17) with positive and negative test scenarios, state transitions, integration sequences, security defenses, and architectural risk mitigations.

---

## 1. Master Test Plan Matrix

| Test ID | Use Case | Scenario Description | Type | Expected Result | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-UC01-01** | UC01 Register | Student registers with valid details, unique email, and roll number | Unit / Flow | Account created, password hashed, redirects to login | Pass |
| **TC-UC01-02** | UC01 Register | Teacher registers with valid details, unique email, and employee ID | Unit / Flow | Account created with teacher role and employee ID | Pass |
| **TC-UC01-03** | UC01 Register | Registration attempted with already registered email | Unit / Negative | Form validation error: email already registered | Pass |
| **TC-UC01-04** | UC01 Register | Registration attempted with weak password (< 8 chars, all numbers) | Unit / Negative | Rejected with standard Django password validator errors | Pass |
| **TC-UC01-05** | UC01 Register | Student registers without supplying mandatory roll number | Unit / Negative | Form rejected: Roll number is required for students | Pass |
| **TC-UC01-06** | UC01 Register | Teacher registers without supplying mandatory employee ID | Unit / Negative | Form rejected: Employee ID is required for teachers | Pass |
| **TC-UC02-01** | UC02 Login | User logs in with correct email and password | Integration | Authenticated session created, redirected to `/dashboard/` | Pass |
| **TC-UC02-02** | UC02 Login | User enters invalid password | Unit / Negative | Generic error message displayed; failed attempt incremented | Pass |
| **TC-UC02-03** | UC02 Login | 5 consecutive failed login attempts for an email | Security | Account locked for 15 minutes; subsequent logins rejected | Pass |
| **TC-UC02-04** | UC02 Login | Locked account login attempt after 15-minute window expires | Security | Lockout lifted automatically; login succeeds with valid credentials | Pass |
| **TC-UC02-05** | UC02 Logout | User submits POST request to `/accounts/logout/` | Security | Session cleared; redirected to login; GET request rejected (405) | Pass |
| **TC-UC03-01** | UC03 Create Project | Teacher creates project with valid title, description, and future deadline | Unit / Flow | Project created with status `Draft`; owner set to current teacher | Pass |
| **TC-UC03-02** | UC03 Create Project | Teacher attempts to create project with deadline in the past | Unit / Negative | Form validation error: deadline cannot be in the past | Pass |
| **TC-UC03-03** | UC03 Edit Project | Teacher edits their own draft/assigned project details | Unit / Flow | Project updated successfully | Pass |
| **TC-UC03-04** | UC03 Edit Project | Teacher attempts to edit another teacher's project | Security / Negative | HTTP 404 Returned; unauthorized modification blocked | Pass |
| **TC-UC03-05** | UC03 Edit Project | Student attempts to access project creation or edit views | Security / Negative | HTTP 403 Forbidden | Pass |
| **TC-UC04-01** | UC04 Assign Project | Teacher assigns project to one or more eligible students | Integration | `ProjectAssignment` records created; project transitions `Draft` -> `Assigned` | Pass |
| **TC-UC04-02** | UC04 Assign Project | Teacher attempts to assign already assigned student | Unit / Edge | Duplicate assignment skipped silently; summary shows "N assigned, M skipped" | Pass |
| **TC-UC04-03** | UC04 Assign Project | Teacher searches students by name and roll number | Unit / Flow | Filtered student list returned accurately | Pass |
| **TC-UC04-04** | UC04 Assign Project | Student attempts to invoke project assignment endpoint | Security / Negative | HTTP 403 Forbidden | Pass |
| **TC-UC05-01** | UC05 View Project | Student views list of assigned projects (`/assignments/my/`) | Integration | Only student's own assigned projects displayed with status & supervisor | Pass |
| **TC-UC05-02** | UC05 View Project | Student opens assignment detail page for own project | Unit / Flow | Progress bar, milestones, supervisor, and deliverable history shown | Pass |
| **TC-UC05-03** | UC05 View Project | Student attempts to view another student's assignment ID | Security / Negative | HTTP 404 Returned; IDOR vulnerability blocked | Pass |
| **TC-UC06-01** | UC06 Project Report | Teacher views progress report for supervised project | Integration | Table shows all assigned students, progress %, days left, status | Pass |
| **TC-UC06-02** | UC06 Project Report | Teacher downloads CSV report for supervised project | System / Flow | Valid CSV file streamed with headers and student rows | Pass |
| **TC-UC06-03** | UC06 Project Report | Teacher attempts to access progress report of another teacher's project | Security / Negative | HTTP 404 Returned | Pass |
| **TC-UC07-01** | UC07 Update Progress | Student updates progress with valid non-decreasing % (e.g. 40% -> 60%) | Unit / Flow | `ProgressUpdate` created; assignment moves `Assigned` -> `In progress` | Pass |
| **TC-UC07-02** | UC07 Update Progress | Student attempts to lower completion percentage (e.g. 60% -> 40%) | Unit / Negative | ValidationError: percentage cannot decrease | Pass |
| **TC-UC07-03** | UC07 Update Progress | Student attempts progress update with percentage > 100 or < 0 | Unit / Negative | ValidationError: percentage must be between 0 and 100 | Pass |
| **TC-UC07-04** | UC07 Update Progress | Student attempts progress update when assignment is `Under review` | Unit / Negative | Operation blocked: updates locked once submitted/reviewed | Pass |
| **TC-UC07-05** | UC07 Update Progress | Student updates progress after teacher requested revision | Integration | Assignment transitions `Revision requested` -> `In progress` | Pass |
| **TC-UC08-01** | UC08 Monitor Progress | Teacher accesses progress monitoring dashboard | Integration | Table displays students, latest %, days remaining, alert flags | Pass |
| **TC-UC08-02** | UC08 Monitor Progress | Assignment past deadline with incomplete status | Unit / Edge | Highlighted with red overdue badge; `mark_overdue` sets `Overdue` | Pass |
| **TC-UC08-03** | UC08 Monitor Progress | Student idle for >= 7 days without update | Unit / Edge | Flagged with amber stale update alert | Pass |
| **TC-UC09-01** | UC09 Progress Report | Teacher generates statistical progress report for project | Unit / Flow | Calculates accurate average progress %, student counts, overdue count | Pass |
| **TC-UC09-02** | UC09 Progress Report | Teacher exports progress report to CSV | System / Flow | Generates `attachment; filename="...csv"` with complete metrics | Pass |
| **TC-UC10-01** | UC10 Submit File | Student uploads valid deliverable PDF (on time) | Integration | File stored under `media/uploads/<id>/<uuid>_<name>`, version auto-increments to v1 | Pass |
| **TC-UC10-02** | UC10 Submit File | Student uploads revision deliverable after revision requested | Integration | Version auto-increments to v2; status transitions to `Submitted` | Pass |
| **TC-UC10-03** | UC10 Submit File | Student attempts to upload empty (0-byte) file | Security / Negative | ValidationError: uploaded file is empty; no DB row or disk file created | Pass |
| **TC-UC10-04** | UC10 Submit File | Student attempts to upload file exceeding MAX_UPLOAD_SIZE (10 MB) | Security / Negative | ValidationError: file exceeds size limit; zero orphaned storage | Pass |
| **TC-UC10-05** | UC10 Submit File | Student uploads `.exe` or disguised binary (`.exe` renamed to `.pdf`) | Security / Negative | File signature inspection rejects PE/binary; validation error | Pass |
| **TC-UC10-06** | UC10 Submit File | Path traversal file name (e.g. `../../etc/passwd.pdf`) | Security / Negative | Filename sanitised to `etc_passwd.pdf`; stored safely inside assignment folder | Pass |
| **TC-UC10-07** | UC10 Submit File | Disk failure simulation during file save | System / Resilience | Atomic transaction rolls back; zero DB records or orphaned files | Pass |
| **TC-UC11-01** | UC11 View Submissions | Teacher lists submissions for supervised projects | Integration | Shows student, version, timestamp, size, On-time vs Late badges | Pass |
| **TC-UC11-02** | UC11 View Submissions | Teacher opens submission detail page | Integration | Transitions assignment `Submitted` -> `Under review` automatically | Pass |
| **TC-UC11-03** | UC11 Download File | Student downloads own submitted file deliverable | System / Flow | Permission verified; streaming `FileResponse` attachment returned | Pass |
| **TC-UC11-04** | UC11 Download File | Student attempts to download another student's file deliverable | Security / Negative | HTTP 403 / 404 Forbidden; unauthorized access blocked | Pass |
| **TC-UC11-05** | UC11 Download File | Teacher attempts to download file from an unsupervised project | Security / Negative | HTTP 404 Returned; strict teacher project isolation enforced | Pass |
| **TC-UC12-01** | UC12 Give Feedback | Teacher enters review comments with revision requested unchecked | Integration | Feedback saved; assignment remains in `Under review` | Pass |
| **TC-UC12-02** | UC12 Give Feedback | Teacher enters review comments with revision requested checked | Integration | Feedback saved; assignment transitions `Under review` -> `Revision requested` | Pass |
| **TC-UC12-03** | UC12 Give Feedback | Teacher attempts feedback on submission of another teacher's project | Security / Negative | HTTP 404 Returned | Pass |
| **TC-UC12-04** | UC12 Give Feedback | Student attempts to submit review feedback | Security / Negative | HTTP 403 Forbidden | Pass |
| **TC-UC13-01** | UC13 View Feedback | Student views feedback on own submission deliverables | Unit / Flow | Comments grouped by version (newest first); revision badges displayed | Pass |
| **TC-UC13-02** | UC13 View Feedback | Student attempts to view feedback of another student's assignment | Security / Negative | HTTP 404 Returned | Pass |
| **TC-UC14-01** | UC14 Assign Marks | Teacher assigns score and max_score to reviewed assignment | Integration | Marks recorded; assignment transitions to `Evaluated` | Pass |
| **TC-UC14-02** | UC14 Assign Marks | Teacher attempts to assign marks before any deliverable is submitted | Unit / Negative | ValidationError: cannot grade assignment without submissions | Pass |
| **TC-UC14-03** | UC14 Assign Marks | Teacher enters score > max_score or negative score | Unit / Negative | ValidationError: score must satisfy 0 <= score <= max_score | Pass |
| **TC-UC14-04** | UC14 Assign Marks | Teacher submits second marks record for same assignment | Unit / Flow | Updates existing record in place; no duplicate rows created | Pass |
| **TC-UC14-05** | UC14 Assign Marks | Last student assignment in project is graded as `Evaluated` | State Transition | Project automatically transitions from `Assigned` to `Closed` | Pass |
| **TC-UC14-06** | UC14 Assign Marks | Teacher attempts to update marks after project is `Closed` | Unit / Negative | ValidationError: cannot modify marks on closed project | Pass |
| **TC-UC15-01** | UC15 View Marks | Student views marks for own evaluated assignment | Unit / Flow | Score, max_score, percentage, grade band, and pass/fail hint shown | Pass |
| **TC-UC15-02** | UC15 View Marks | Student attempts to view marks before assignment is `Evaluated` | Unit / Negative | HTTP 404 Returned; grades hidden until evaluation is complete | Pass |
| **TC-UC15-03** | UC15 View Marks | Student attempts to view marks of another student's assignment | Security / Negative | HTTP 404 Returned | Pass |
| **TC-UC16-01** | UC16 Marks Report | Teacher generates marks summary report for project | Unit / Flow | Displays all students, scores, grade bands, average, highest, lowest | Pass |
| **TC-UC16-02** | UC16 Marks Report | Teacher downloads marks report as CSV | System / Flow | Streams formatted CSV with student grades and class statistics | Pass |
| **TC-UC16-03** | UC16 Marks Report | Teacher attempts marks report on another teacher's project | Security / Negative | HTTP 404 Returned | Pass |
| **TC-UC17-01** | UC17 Dashboard | Student views dashboard (`/dashboard/`) | Integration | Projects categorized by status, 7-day deadlines, latest feedback/marks shown | Pass |
| **TC-UC17-02** | UC17 Dashboard | Teacher views dashboard (`/dashboard/`) | Integration | Project cards, KPI status counters, review queue, Chart.js chart shown | Pass |
| **TC-UC17-03** | UC17 Dashboard | Student attempts to access teacher dashboard data | Security / Negative | HTTP 403 or role-segregated student template rendered without teacher data | Pass |
| **TC-UC17-04** | UC17 Notifications | Action triggers event notification (assignment, submission, feedback, marks) | Integration | In-app notification created; email sent via `send_email` | Pass |
| **TC-UC17-05** | UC17 Notifications | Email server failure simulation (SMTP down) | Integration / Resilience | Caught, logged, returns False; main workflow completes without interruption | Pass |
| **TC-UC17-06** | UC17 Notifications | Student marks in-app notification as read | Unit / Flow | `is_read` updated to True; unread navbar badge count decrements | Pass |
| **TC-UC17-07** | UC17 Reminders | `send_deadline_reminders` command runs for deadline in 2 days | System / CLI | Reminder sent to student; `deadline_reminder_sent` set; duplicate run sends 0 | Pass |

---

## 2. State Machine Transitions Matrix

### 2.1 Project Lifecycle Transitions
| Initial State | Target State | Triggering Action | Valid? |
| :--- | :--- | :--- | :--- |
| `Draft` | `Assigned` | Teacher assigns first student to project | Yes |
| `Draft` | `Closed` | Manual close without assignments | Yes |
| `Assigned` | `Closed` | All assigned students evaluated | Yes |
| `Closed` | `Draft` | Reopen attempt | Illegal (Raises `InvalidTransition`) |
| `Closed` | `Assigned` | Assign additional student to closed project | Illegal (Raises `InvalidTransition`) |

### 2.2 Student Assignment Lifecycle Transitions
| Initial State | Target State | Triggering Action | Valid? |
| :--- | :--- | :--- | :--- |
| `Assigned` | `In progress` | Student posts first milestone progress update | Yes |
| `Assigned` | `Submitted` | Student directly submits deliverable v1 | Yes |
| `Assigned` | `Overdue` | Project deadline passes without milestone activity | Yes |
| `In progress` | `Submitted` | Student uploads project deliverable | Yes |
| `In progress` | `Overdue` | Deadline passes while work is in progress | Yes |
| `Overdue` | `Submitted` | Student submits late deliverable | Yes |
| `Submitted` | `Under review` | Supervising teacher opens submission review | Yes |
| `Under review` | `Revision requested` | Teacher reviews and ticks "Request revision" | Yes |
| `Under review` | `Evaluated` | Teacher assigns final marks | Yes |
| `Revision requested` | `In progress` | Student updates progress after revision request | Yes |
| `Revision requested` | `Submitted` | Student submits Version 2 deliverable | Yes |
| `Evaluated` | `In progress` | Attempt to revert evaluation | Illegal (Raises `InvalidTransition`) |
| `Submitted` | `In progress` | Student attempts progress update while submitted | Illegal (Raises `InvalidTransition`) |

---

## 3. Risk Analysis and Verification (R4, R7, R8, R9)

### Risk R4: External Integration Failures (Email & Notification)
- **Threat**: Mail server downtime or network timeouts during SMTP dispatch.
- **Mitigation**: `dashboard/notifications.py :: send_email()` wraps all email operations in `try...except Exception`, logs the failure with context, and returns `False`.
- **Verification**: `test_email_failure_does_not_break_services` verifies that project assignment, file submission, review feedback, and marks assignment commit successfully even when `send_mail` raises `SMTPException`.

### Risk R7: Security & Authorization Vulnerabilities
- **Threat**: IDOR, privilege escalation, CSRF, XSS, SQL injection, brute-force credential stuffing.
- **Mitigation**:
  - Strict role decorators (`@teacher_required`, `@student_required`) and `login_required`.
  - Object-level ownership filters on all queries (teachers only see supervised projects; students only see own deliverables).
  - CSRF middleware active across all state-changing POST requests.
  - Django template auto-escaping blocks stored XSS in project titles and review comments.
  - Django ORM parameterized queries prevent SQL injection across all search inputs.
  - Account lockout after 5 consecutive failed login attempts (15-minute lock).
  - PBKDF2 password hashing; plain-text passwords never stored.
- **Verification**: Comprehensive automated security test suite in `tests/security/test_security_suite.py`.

### Risk R8: Data Loss & Transaction Atomicity
- **Threat**: Discrepancies between filesystem storage and relational database metadata upon failure.
- **Mitigation**: `submissions/services.py :: submit_file()` executes within `transaction.atomic()`. If database creation fails, disk files are immediately cleaned up. If disk write fails, the database transaction rolls back.
- **Verification**: `test_submit_file_rollback_on_db_error` verifies zero phantom DB rows and zero orphaned files on disk.

### Risk R9: Malicious & Unsafe File Uploads
- **Threat**: Upload of executable binaries, scripts disguised as PDFs, path traversal, decompression bombs, or oversized payloads.
- **Mitigation**:
  - File extension whitelist check (`ALLOWED_UPLOAD_EXTENSIONS`).
  - Magic byte / signature inspection checking first 4–8 bytes to detect PE (`MZ`), ELF, and Mach-O binaries regardless of filename extension.
  - Filename sanitization stripping directory markers, leading dots, and unsafe characters.
  - Strict file size enforcement against `MAX_UPLOAD_SIZE` (10 MB).
  - Empty file detection (0-byte rejection).
- **Verification**: Dedicated test cases in `submissions/tests/test_submissions.py` and `tests/security/test_security_suite.py`.
