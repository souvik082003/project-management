# PMS Operations & Deployment Guide

This document outlines recurring operational tasks, scheduled cron jobs, environment configurations, and production maintenance procedures for the Academic Project Management System (PMS).

---

## 1. Automated Cron Jobs

PMS includes two primary automated maintenance commands that must be scheduled via system crontab in production.

### Daily Schedule

```cron
# ==============================================================================
# Academic Project Management System (PMS) Crontab
# ==============================================================================

# 1. Mark Overdue Assignments (Runs daily at midnight 00:01)
# Inspects active 'In progress' assignments whose project deadline has lapsed and
# transitions them to 'Overdue'.
1 0 * * * cd /var/www/pms && /var/www/pms/.venv/bin/python manage.py mark_overdue >> /var/log/pms/cron.log 2>&1

# 2. Send 2-Day Deadline Reminders (Runs daily at 08:00 AM)
# Dispatches automated email notifications and in-app alerts to students whose
# deliverables are due in 2 days. Guarantees single delivery per assignment.
0 8 * * * cd /var/www/pms && /var/www/pms/.venv/bin/python manage.py send_deadline_reminders >> /var/log/pms/cron.log 2>&1
```

### Manual Command Execution

```bash
# Transition overdue assignments manually:
python manage.py mark_overdue

# Dispatch upcoming deadline reminders manually:
python manage.py send_deadline_reminders
```

---

## 2. Environment Variables & Production Configuration

Production configuration resides in `pms/settings/prod.py`. Ensure the following environment variables are securely supplied via system environment or `.env`:

| Variable | Description | Example / Default |
| :--- | :--- | :--- |
| `SECRET_KEY` | High-entropy production cryptographic secret | *(Unique secret string)* |
| `DEBUG` | Disabled in production | `False` |
| `ALLOWED_HOSTS` | Authorized domain names | `pms.university.edu,10.0.0.5` |
| `DB_ENGINE` | Production database backend | `django.db.backends.mysql` |
| `DB_NAME` | Database schema name | `pms_db` |
| `DB_USER` | Database user | `pms_admin` |
| `DB_PASSWORD` | Database user password | *(Strong password)* |
| `DB_HOST` | Database host | `127.0.0.1` |
| `DB_PORT` | Database port | `3306` |
| `EMAIL_BACKEND` | Production SMTP email backend | `django.core.mail.backends.smtp.EmailBackend` |
| `EMAIL_HOST` | SMTP server hostname | `smtp.mailgun.org` / `smtp.gmail.com` |
| `EMAIL_PORT` | SMTP port | `587` |
| `EMAIL_USE_TLS` | Enable STARTTLS | `True` |
| `EMAIL_HOST_USER` | SMTP authentication user | `postmaster@pms.university.edu` |
| `EMAIL_HOST_PASSWORD` | SMTP authentication credential | *(SMTP Secret)* |
| `DEFAULT_FROM_EMAIL`| Outgoing notifications sender header | `PMS Notifications <noreply@pms.university.edu>` |
| `MAX_UPLOAD_SIZE` | Maximum deliverable file upload size | `10485760` (10 MB) |
| `PMS_PASSING_PERCENTAGE` | Academic passing mark threshold | `40.0` (40%) |

---

## 3. Storage & Security Architecture

1. **Deliverables Storage Isolation:**
   - Uploaded files are written directly to disk under `MEDIA_ROOT/uploads/<assignment_id>/<uuid>_<safe_name>`.
   - Django never serves `MEDIA_ROOT` publicly in production (`settings.DEBUG=False`).
   - Downloads are streamed strictly through `submissions:download_submission` which enforces role-based ownership validation (`FileResponse(as_attachment=True)`).
2. **Logging & Monitoring:**
   - Application events and notification logs are written to `logs/pms.log` with automatic log rotation (5 MB per file, 5 backups preserved).
3. **Database Transactions & Cleanup:**
   - File uploads and mark assignments utilize atomic database transactions (`transaction.atomic()`). If database persistence fails, orphaned disk files are automatically purged immediately.
