#!/usr/bin/env python
"""
Seed script to populate realistic academic demo data for the PMS project.
Usage:
    python scripts/seed_demo_data.py
"""
import os
import sys
from pathlib import Path
from datetime import timedelta

# Set up Django environment
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'pms.settings.dev')

import django
django.setup()

from django.utils import timezone
from accounts.models import User, UserRole
from projects.models import Project, ProjectStatus
from assignments.models import ProjectAssignment, AssignmentStatus
from progress.models import ProgressUpdate
from submissions.models import Submission
from reviews.models import Feedback, Marks
from dashboard.models import Notification

def seed():
    print("Clearing old demo data...")
    Notification.objects.all().delete()
    Marks.objects.all().delete()
    Feedback.objects.all().delete()
    Submission.objects.all().delete()
    ProgressUpdate.objects.all().delete()
    ProjectAssignment.objects.all().delete()
    Project.objects.all().delete()
    User.objects.all().delete()

    print("Creating user accounts...")
    # Admin / Coordinator
    admin_user = User.objects.create_superuser(
        username="admin@example.edu",
        email="admin@example.edu",
        password="AdminPassword@2026",
        name="System Administrator",
        role=UserRole.TEACHER,
        department="Computer Science & Engineering",
        employee_id="ADM001"
    )

    # Teachers
    teacher_sharma = User.objects.create_user(
        username="prof.sharma@example.edu",
        email="prof.sharma@example.edu",
        password="TeacherPassword@2026",
        name="Prof. Rajesh Sharma",
        role=UserRole.TEACHER,
        department="Computer Science & Engineering",
        employee_id="TCH001"
    )

    teacher_anita = User.objects.create_user(
        username="dr.anita@example.edu",
        email="dr.anita@example.edu",
        password="TeacherPassword@2026",
        name="Dr. Anita Sen",
        role=UserRole.TEACHER,
        department="Information Technology",
        employee_id="TCH002"
    )

    # Students
    student_rahul = User.objects.create_user(
        username="rahul.verma@example.edu",
        email="rahul.verma@example.edu",
        password="StudentPassword@2026",
        name="Rahul Verma",
        role=UserRole.STUDENT,
        department="Computer Science & Engineering",
        roll_no="CS202201"
    )

    student_priya = User.objects.create_user(
        username="priya.patel@example.edu",
        email="priya.patel@example.edu",
        password="StudentPassword@2026",
        name="Priya Patel",
        role=UserRole.STUDENT,
        department="Computer Science & Engineering",
        roll_no="CS202202"
    )

    student_arjun = User.objects.create_user(
        username="arjun.nair@example.edu",
        email="arjun.nair@example.edu",
        password="StudentPassword@2026",
        name="Arjun Nair",
        role=UserRole.STUDENT,
        department="Computer Science & Engineering",
        roll_no="CS202203"
    )

    now = timezone.now()

    print("Creating academic projects...")
    # Project 1: Active, Assigned
    proj_drone = Project.objects.create(
        title="Autonomous Drone Navigation System",
        description="Design and implement a real-time obstacle avoidance and path planning algorithm for quadcopters using ROS and OpenCV.",
        deadline=now + timedelta(days=12),
        status=ProjectStatus.ASSIGNED,
        created_by=teacher_sharma
    )

    # Project 2: Active, Assigned
    proj_kv = Project.objects.create(
        title="Distributed Key-Value Store with Raft Consensus",
        description="Build a fault-tolerant, horizontally scalable key-value storage engine implementing leader election, log replication, and snapshotting.",
        deadline=now + timedelta(days=2),
        status=ProjectStatus.ASSIGNED,
        created_by=teacher_sharma
    )

    # Project 3: Closed (Fully evaluated)
    proj_vision = Project.objects.create(
        title="AI-Powered Medical Image Segmentation",
        description="Develop deep learning models (UNet/Vision Transformer) for automated tumor segmentation in MRI scans.",
        deadline=now - timedelta(days=10),
        status=ProjectStatus.CLOSED,
        created_by=teacher_sharma
    )

    # Project 4: Draft project by Dr. Anita
    proj_iot = Project.objects.create(
        title="Smart Campus IoT Energy Monitoring",
        description="Deploy wireless sensor nodes to monitor power consumption in lecture halls with predictive peak-load anomaly detection.",
        deadline=now + timedelta(days=25),
        status=ProjectStatus.DRAFT,
        created_by=teacher_anita
    )

    print("Creating assignments and workflows...")

    # --- Rahul on Drone Navigation (Under Review) ---
    asgn_rahul_drone = ProjectAssignment.objects.create(
        project=proj_drone,
        student=student_rahul,
        status=AssignmentStatus.UNDER_REVIEW
    )
    asgn_rahul_drone.assigned_on = now - timedelta(days=20)
    asgn_rahul_drone.save()

    ProgressUpdate.objects.create(
        assignment=asgn_rahul_drone,
        percent_complete=30,
        remarks="Completed literature survey and mathematical formulation of path planning.",
        updated_on=now - timedelta(days=15)
    )
    ProgressUpdate.objects.create(
        assignment=asgn_rahul_drone,
        percent_complete=65,
        remarks="Simulated ROS nodes in Gazebo; obstacle detection working in simulation.",
        updated_on=now - timedelta(days=8)
    )
    ProgressUpdate.objects.create(
        assignment=asgn_rahul_drone,
        percent_complete=85,
        remarks="Hardware integration and initial field test logs recorded.",
        updated_on=now - timedelta(days=2)
    )

    # Fake sample file in media
    upload_dir = BASE_DIR / 'media' / 'uploads' / str(asgn_rahul_drone.id)
    upload_dir.mkdir(parents=True, exist_ok=True)
    sample_file = upload_dir / "drone_interim_report_v1.pdf"
    sample_file.write_bytes(b"%PDF-1.4\n%Demo PDF Content for Drone Navigation Project Deliverable\n%%EOF")

    sub_rahul_drone = Submission.objects.create(
        assignment=asgn_rahul_drone,
        file_path=str(sample_file),
        file_name="drone_interim_report_v1.pdf",
        file_size=sample_file.stat().st_size,
        version=1,
        submitted_on=now - timedelta(days=2)
    )

    Feedback.objects.create(
        submission=sub_rahul_drone,
        teacher=teacher_sharma,
        comments="Solid progress on Gazebo simulation. Please include the field trial video link and motor telemetry graphs in the next section.",
        requested_revision=False,
        given_on=now - timedelta(days=1)
    )

    # --- Priya on Drone Navigation (In Progress) ---
    asgn_priya_drone = ProjectAssignment.objects.create(
        project=proj_drone,
        student=student_priya,
        status=AssignmentStatus.IN_PROGRESS
    )
    asgn_priya_drone.assigned_on = now - timedelta(days=20)
    asgn_priya_drone.save()

    ProgressUpdate.objects.create(
        assignment=asgn_priya_drone,
        percent_complete=50,
        remarks="Completed camera calibration and feature matching with OpenCV.",
        updated_on=now - timedelta(days=4)
    )

    # --- Arjun on Drone Navigation (Assigned, Not started) ---
    asgn_arjun_drone = ProjectAssignment.objects.create(
        project=proj_drone,
        student=student_arjun,
        status=AssignmentStatus.ASSIGNED
    )
    asgn_arjun_drone.assigned_on = now - timedelta(days=10)
    asgn_arjun_drone.save()

    # --- Rahul on Raft Key-Value Store (In Progress, Deadline in 2 days) ---
    asgn_rahul_kv = ProjectAssignment.objects.create(
        project=proj_kv,
        student=student_rahul,
        status=AssignmentStatus.IN_PROGRESS
    )
    asgn_rahul_kv.assigned_on = now - timedelta(days=14)
    asgn_rahul_kv.save()

    ProgressUpdate.objects.create(
        assignment=asgn_rahul_kv,
        percent_complete=40,
        remarks="Leader election RPC protocol implemented and verified with mock network partitions.",
        updated_on=now - timedelta(days=3)
    )

    # --- Rahul on Medical Image Segmentation (Evaluated / Closed) ---
    asgn_rahul_vision = ProjectAssignment.objects.create(
        project=proj_vision,
        student=student_rahul,
        status=AssignmentStatus.EVALUATED
    )
    asgn_rahul_vision.assigned_on = now - timedelta(days=40)
    asgn_rahul_vision.save()

    ProgressUpdate.objects.create(
        assignment=asgn_rahul_vision,
        percent_complete=100,
        remarks="Final thesis defense and benchmark evaluation complete against BraTS dataset.",
        updated_on=now - timedelta(days=11)
    )

    vision_upload_dir = BASE_DIR / 'media' / 'uploads' / str(asgn_rahul_vision.id)
    vision_upload_dir.mkdir(parents=True, exist_ok=True)
    vision_file = vision_upload_dir / "final_thesis_report.pdf"
    vision_file.write_bytes(b"%PDF-1.4\n%Final Thesis on AI Medical Image Segmentation\n%%EOF")

    sub_rahul_vision = Submission.objects.create(
        assignment=asgn_rahul_vision,
        file_path=str(vision_file),
        file_name="final_thesis_report.pdf",
        file_size=vision_file.stat().st_size,
        version=1,
        submitted_on=now - timedelta(days=12)
    )

    Feedback.objects.create(
        submission=sub_rahul_vision,
        teacher=teacher_sharma,
        comments="Outstanding thesis presentation and thorough quantitative validation. Model achieved 91.4% Dice score.",
        requested_revision=False,
        given_on=now - timedelta(days=10)
    )

    Marks.objects.create(
        assignment=asgn_rahul_vision,
        teacher=teacher_sharma,
        score=94.0,
        max_score=100.0,
        graded_on=now - timedelta(days=10)
    )

    print("Generating demo in-app notifications...")
    Notification.objects.create(
        user=student_rahul,
        message="Prof. Rajesh Sharma reviewed your submission for 'Autonomous Drone Navigation System'.",
        link=f"/reviews/assignment/{asgn_rahul_drone.id}/feedback/",
        is_read=False,
        created_at=now - timedelta(days=1)
    )
    Notification.objects.create(
        user=student_rahul,
        message="Marks published for 'AI-Powered Medical Image Segmentation': 94.0 / 100.0 (Grade A+)",
        link=f"/reviews/assignment/{asgn_rahul_vision.id}/marks/view/",
        is_read=False,
        created_at=now - timedelta(days=10)
    )
    Notification.objects.create(
        user=teacher_sharma,
        message=f"New deliverable submitted by Rahul Verma for 'Autonomous Drone Navigation System'.",
        link=f"/reviews/submission/{sub_rahul_drone.id}/feedback/",
        is_read=False,
        created_at=now - timedelta(days=2)
    )
    Notification.objects.create(
        user=student_rahul,
        message="Friendly reminder: Deadline for 'Distributed Key-Value Store with Raft Consensus' is in 2 days.",
        link=f"/assignments/{asgn_rahul_kv.id}/",
        is_read=False,
        created_at=now - timedelta(hours=6)
    )

    print("Seed completed successfully!")
    print("\n--- DEMO LOGIN CREDENTIALS ---")
    print("Teacher Login:")
    print("  Email:    prof.sharma@example.edu")
    print("  Password: TeacherPassword@2026")
    print("\nStudent Login:")
    print("  Email:    rahul.verma@example.edu")
    print("  Password: StudentPassword@2026")
    print("\nAdmin Login:")
    print("  Email:    admin@example.edu")
    print("  Password: AdminPassword@2026")
    print("--------------------------------")

if __name__ == '__main__':
    seed()
