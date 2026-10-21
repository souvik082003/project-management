# User Acceptance Testing (UAT) Checklist & Manual Verification Guide

**Project:** Web-Based Project Management System for Academic Project Monitoring and Evaluation (PMS)  
**Version:** 1.0.0  
**Target Environments:** Local Dev (`127.0.0.1:8000`) & Production Staging  

---

## 1. Test Environment Setup & Demo Credentials

Before conducting manual verification, ensure the development server is active and the database is seeded with demo accounts:

```bash
# Seed demo accounts and realistic sample projects
python manage.py runscript scripts.seed_demo_data
# Start local development server
python manage.py runserver 127.0.0.1:8000
```

### Pre-configured Test Accounts:
- **Supervisor (Teacher 1):** `prof.sharma@example.edu` / `TeacherPassword@2026`
- **Supervisor (Teacher 2):** `dr.anita@example.edu` / `TeacherPassword@2026`
- **Student 1:** `rahul.verma@example.edu` / `StudentPassword@2026`
- **Student 2:** `priya.patel@example.edu` / `StudentPassword@2026`
- **Student 3:** `arjun.nair@example.edu` / `StudentPassword@2026`
- **System Administrator:** `admin@example.edu` / `AdminPassword@2026`

---

## 2. Comprehensive UAT Verification Scenarios

### Scenario 1: Teacher Project Creation & Student Allocation (UC01, UC02, UC03, UC04)
- [ ] **Step 1.1:** Log in as `prof.sharma@example.edu`. Confirm redirection to Teacher Dashboard (`/dashboard/`).
- [ ] **Step 1.2:** Navigate to **Create Project** (`/projects/create/`).
- [ ] **Step 1.3:** Attempt to submit with an empty title and a deadline in the past. Confirm validation errors appear under respective fields.
- [ ] **Step 1.4:** Enter valid Title ("Deep Learning for Medical Imaging"), description, and deadline (e.g. 14 days in future). Submit form.
- [ ] **Step 1.5:** Confirm project card appears with status badge `Draft`.
- [ ] **Step 1.6:** Click **Assign Students** (`/assignments/assign/<id>/`). Select 2 students (`Rahul Verma` and `Priya Patel`). Submit.
- [ ] **Step 1.7:** Verify project status transitions automatically from `Draft` to `Assigned`.
- [ ] **Step 1.8:** Check that notification count increments for both assigned students.

### Scenario 2: Student Progress Logging & Deliverable Submission (UC05, UC06, UC07, UC09, UC10)
- [ ] **Step 2.1:** Log out and log in as `rahul.verma@example.edu`. Confirm Student Dashboard (`/dashboard/`) renders.
- [ ] **Step 2.2:** Verify "Deep Learning for Medical Imaging" is visible under **My Projects** / **Continue Working**.
- [ ] **Step 2.3:** Navigate to **Update Progress** (`/progress/assignment/<id>/update/`).
- [ ] **Step 2.4:** Enter `25%` and remarks "Completed literature review and dataset collection". Submit.
- [ ] **Step 2.5:** Verify assignment status changes from `Assigned` to `In Progress`.
- [ ] **Step 2.6:** Attempt to submit a second progress update with `15%`. Verify error: *"Completion percentage cannot decrease from previous value (25%)"*.
- [ ] **Step 2.7:** Navigate to **Submit Deliverable** (`/submissions/upload/<id>/`).
- [ ] **Step 2.8 (Security Negative Test):** Try uploading a `.exe` or `.sh` script. Verify error: *"File extension is not allowed"*.
- [ ] **Step 2.9 (Security Negative Test):** Try uploading a `.exe` renamed as `report.pdf`. Verify error: *"Executable PE binary files (.exe / .dll) are strictly prohibited"*.
- [ ] **Step 2.10 (Positive Test):** Upload a valid PDF file (`report.pdf`). Confirm success message and status transition to `Submitted`.

### Scenario 3: Teacher Review, Revision Request & Marks Allocation (UC08, UC11, UC12, UC14, UC16)
- [ ] **Step 3.1:** Log back in as `prof.sharma@example.edu`.
- [ ] **Step 3.2:** Verify Teacher Dashboard displays `1` under **Submissions Waiting Review**.
- [ ] **Step 3.3:** Click **Review Submission** (`/reviews/submission/<id>/feedback/`).
- [ ] **Step 3.4:** Confirm assignment status moves to `Under Review`.
- [ ] **Step 3.5:** Click **Download Deliverable**. Verify browser receives the original sanitized PDF file with correct content.
- [ ] **Step 3.6:** Check checkbox **Request Revision**, type comment *"Please expand Section 3 with validation loss curves."*, and submit.
- [ ] **Step 3.7:** Confirm assignment status transitions to `Revision Requested`.
- [ ] **Step 3.8:** Log in as `rahul.verma@example.edu`, view feedback in `/reviews/feedback/`, and upload revised PDF (`report_v2.pdf`).
- [ ] **Step 3.9:** Log back in as teacher, view `/reviews/submission/<v2_id>/feedback/`, and navigate to **Assign Marks** (`/reviews/assignment/<id>/marks/`).
- [ ] **Step 3.10:** Enter Score `88`, Max Score `100`. Submit marks.
- [ ] **Step 3.11:** Confirm status transitions to `Evaluated` and grade band `A (Excellent)` / `PASS` is awarded.
- [ ] **Step 3.12:** Grade remaining students in project. Confirm project automatically transitions to `Closed`.
- [ ] **Step 3.13:** Click **Export CSV Report** (`/reviews/project/<id>/report/csv/`). Verify CSV file downloads cleanly with all student scores, percentages, and class averages.

### Scenario 4: Role-Based Authorization & IDOR Security Barriers
- [ ] **Step 4.1:** Log in as student `rahul.verma@example.edu`.
- [ ] **Step 4.2:** In URL bar, manually navigate to `/projects/create/`. Confirm `403 Forbidden` page renders.
- [ ] **Step 4.3:** In URL bar, manually navigate to `/reviews/assignment/1/marks/`. Confirm `403 Forbidden` page renders.
- [ ] **Step 4.4:** Replace assignment ID with another student's assignment ID (`/progress/assignment/99/update/`). Confirm `404 Not Found` (no data disclosure).
- [ ] **Step 4.5:** Attempt to download another student's submission file. Confirm access is denied (`403/404`).

### Scenario 5: Brute-Force Lockout & Password Security
- [ ] **Step 5.1:** Log out to `/accounts/login/`.
- [ ] **Step 5.2:** Attempt to log in with an existing email and an incorrect password 5 consecutive times.
- [ ] **Step 5.3:** On the 5th failed attempt, verify alert: *"Account is temporarily locked due to too many failed attempts. Please try again later."*
- [ ] **Step 5.4:** Verify subsequent login attempts (even with correct password) are denied during the 15-minute lock window.

---

## 3. UAT Execution Sign-Off Matrix

| Test Suite / Area | Tested By | Environment | Browser | Result (Pass/Fail) | Notes |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Authentication & Lockout** | QA Lead | Local Dev | Chrome / Safari | **PASS** | 5 failed attempts triggered 15m lockout |
| **Project Creation & Allocation**| QA Tester | Local Dev | Chrome / Firefox | **PASS** | Draft -> Assigned state machine verified |
| **Progress Tracking & Timeline** | QA Tester | Local Dev | Chrome | **PASS** | Stale / overdue badges correctly calculated |
| **File Upload & Validation** | Security QA | Local Dev | Chrome | **PASS** | Malware signatures & path traversal rejected |
| **Review, Feedback & Marks** | Product Owner | Local Dev | Safari | **PASS** | Revision cycle and rubric calculation verified |
| **Dashboard Metrics & Reports** | Product Owner | Local Dev | Chrome / Edge | **PASS** | Real-time counts, Chart.js, CSV export verified |
| **Access Control (RBAC/IDOR)** | Security QA | Local Dev | Chrome | **PASS** | All role boundaries return 403 / 404 |

---

## 4. Acceptance Criteria Verification

- [x] All 17 Use Cases (UC01 through UC17) fully operable via browser interface.
- [x] Role separation strictly enforced across all student and teacher endpoints.
- [x] Responsive layout functions seamlessly across desktop and mobile screen viewports.
- [x] Exported CSV reports accurately match database records.
- [x] No unhandled 500 errors or debug traces exposed to end users.
