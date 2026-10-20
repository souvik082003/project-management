# Web-Based Project Management System (PMS)
### Academic Project Monitoring and Evaluation

An institutional web-based platform for academic project monitoring, file submission versioning, progress tracking, and iterative review/evaluation.

---

## 🛠 Technology Stack
- **Backend:** Python 3.11+, Django 5.x
- **Frontend:** Server-rendered Django Templates, Bootstrap 5, Vanilla JavaScript
- **Database:** SQLite (Development) / MySQL (Production)
- **Configuration:** Environment-driven via `python-decouple`
- **Testing:** Django `TestCase`, `coverage.py`

---

## 🏛 Architecture (Strict 4-Layer Pattern)
```
View / Template
      │
      ▼
views.py (Request parsing, role verification, template rendering)
      │
      ▼
services.py (ALL business rules, state machines, notification triggers)
      │
      ▼
models / ORM (Database persistence & relations)
```

---

## 🚀 Quick Start & Setup

### 1. Prerequisites
- Python 3.11 or higher
- Git

### 2. Environment Setup
```bash
# Clone the repository
git clone <repo-url>
cd "project management"

# Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Create environment file
cp .env.example .env
```

### 3. Database Migration
```bash
python manage.py makemigrations
python manage.py migrate
```

### 4. Run Development Server
```bash
python manage.py runserver
```
Visit `http://127.0.0.1:8000/` in your browser.

---

## 🧪 Running Tests & Coverage

```bash
# Run unit and smoke tests
python manage.py test

# Run tests with coverage
coverage run --source='.' manage.py test
coverage report
```

---

## 📁 Repository Structure
- `pms/`: Project configuration and settings (`settings/base.py`, `dev.py`, `prod.py`).
- `accounts/`: Authentication and role management (`accounts.User`).
- `projects/`: Project creation, editing, and listing.
- `assignments/`: Student-project allocation and status state machine.
- `progress/`: Progress milestone tracking and percentage validation.
- `submissions/`: File uploads, extensions, size validation, and versioning.
- `reviews/`: Teacher feedback and numerical scoring / marks.
- `dashboard/`: Role-tailored dashboards and alerts.
- `templates/`: Base layout, navigation bars, and reusable components.
- `static/`: CSS and vanilla JavaScript assets.
- `media/`: Uploaded files storage (gitignored).
- `docs/`: System documentation and changelog.
