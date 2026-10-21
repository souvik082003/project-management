"""
Real email notification service and in-app alert dispatcher.
Provides fault-tolerant email dispatching wrapped around Django's send_mail.
Never raises exceptions into calling business logic services.
"""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from .models import Notification

logger = logging.getLogger('pms')


def send_email(to: str, subject: str, body: str, html_body: str = None) -> bool:
    """
    Core wrapper around Django send_mail.
    Catches all exceptions, logs them, returns False.
    Never raises an exception into the caller.
    """
    try:
        from_email = getattr(settings, 'DEFAULT_FROM_EMAIL', 'pms-noreply@example.edu')
        send_mail(
            subject=subject,
            message=body,
            from_email=from_email,
            recipient_list=[to],
            html_message=html_body,
            fail_silently=False
        )
        logger.info(f"Email successfully sent to '{to}': '{subject}'")
        return True
    except Exception as err:
        logger.error(f"Failed to send email to '{to}' (subject: '{subject}'): {err}")
        return False


def _create_in_app_notification(user, message: str, link: str = ""):
    """Helper to safely record an in-app notification without breaking caller."""
    try:
        Notification.objects.create(
            user=user,
            message=message,
            link=link
        )
    except Exception as err:
        logger.warning(f"Failed to create in-app notification for {user}: {err}")


def notify_assignment(assignment) -> bool:
    """
    Sends email notification to student upon project assignment allocation.
    """
    student = assignment.student
    project = assignment.project
    subject = f"New Project Assigned: {project.title}"

    context = {
        'student': student,
        'project': project,
        'assignment': assignment,
    }

    try:
        body = render_to_string('emails/assignment_notification.txt', context)
        html_body = render_to_string('emails/assignment_notification.html', context)
    except Exception as t_err:
        logger.error(f"Failed to render assignment email template: {t_err}")
        body = f"Hello {student.get_display_name()},\nYou have been assigned to project '{project.title}'."
        html_body = None

    link = f"/assignments/{assignment.id}/"
    _create_in_app_notification(
        user=student,
        message=f"You were assigned to project '{project.title}' by {project.created_by.get_display_name()}.",
        link=link
    )

    return send_email(to=student.email, subject=subject, body=body, html_body=html_body)


def notify_teacher_new_submission(submission) -> bool:
    """
    Sends email notification to supervising teacher when student submits a deliverable.
    """
    assignment = submission.assignment
    teacher = assignment.project.created_by
    student = assignment.student
    project = assignment.project
    subject = f"New Submission (v{submission.version}): {project.title}"

    context = {
        'teacher': teacher,
        'student': student,
        'project': project,
        'submission': submission,
    }

    try:
        body = render_to_string('emails/submission_notification.txt', context)
        html_body = render_to_string('emails/submission_notification.html', context)
    except Exception as t_err:
        logger.error(f"Failed to render submission email template: {t_err}")
        body = f"Hello {teacher.get_display_name()},\n{student.get_display_name()} submitted version {submission.version} for '{project.title}'."
        html_body = None

    link = f"/submissions/{submission.id}/"
    _create_in_app_notification(
        user=teacher,
        message=f"Student {student.get_display_name()} submitted v{submission.version} for '{project.title}'.",
        link=link
    )

    return send_email(to=teacher.email, subject=subject, body=body, html_body=html_body)


def notify_feedback(feedback) -> bool:
    """
    Sends email notification to student when teacher provides review comments.
    """
    submission = feedback.submission
    assignment = submission.assignment
    student = assignment.student
    project = assignment.project
    teacher = feedback.teacher

    subject = f"Feedback on Submission (v{submission.version}): {project.title}"

    context = {
        'student': student,
        'teacher': teacher,
        'project': project,
        'submission': submission,
        'feedback': feedback,
    }

    try:
        body = render_to_string('emails/feedback_notification.txt', context)
        html_body = render_to_string('emails/feedback_notification.html', context)
    except Exception as t_err:
        logger.error(f"Failed to render feedback email template: {t_err}")
        body = f"Hello {student.get_display_name()},\nNew feedback received for '{project.title}' from {teacher.get_display_name()}."
        html_body = None

    link = f"/reviews/assignment/{assignment.id}/feedback/"
    rev_msg = " (Revision requested)" if feedback.requested_revision else ""
    _create_in_app_notification(
        user=student,
        message=f"Supervisor feedback given on v{submission.version} for '{project.title}'{rev_msg}.",
        link=link
    )

    return send_email(to=student.email, subject=subject, body=body, html_body=html_body)


def notify_marks(marks) -> bool:
    """
    Sends email notification to student when evaluation marks and grades are published.
    """
    assignment = marks.assignment
    student = assignment.student
    project = assignment.project
    teacher = marks.teacher

    subject = f"Evaluation Completed: Marks Published for {project.title}"

    context = {
        'student': student,
        'teacher': teacher,
        'project': project,
        'marks': marks,
    }

    try:
        body = render_to_string('emails/marks_notification.txt', context)
        html_body = render_to_string('emails/marks_notification.html', context)
    except Exception as t_err:
        logger.error(f"Failed to render marks email template: {t_err}")
        body = f"Hello {student.get_display_name()},\nMarks published for '{project.title}': {marks.score}/{marks.max_score} ({marks.percentage}%)."
        html_body = None

    link = f"/reviews/assignment/{assignment.id}/marks/view/"
    _create_in_app_notification(
        user=student,
        message=f"Evaluation completed for '{project.title}': {marks.score}/{marks.max_score} (Grade {marks.grade_band}).",
        link=link
    )

    return send_email(to=student.email, subject=subject, body=body, html_body=html_body)


def notify_deadline_reminder(assignment) -> bool:
    """
    Sends automated email reminder 2 days before project deadline.
    """
    student = assignment.student
    project = assignment.project
    subject = f"Upcoming Deadline Reminder: {project.title}"

    context = {
        'student': student,
        'project': project,
        'assignment': assignment,
    }

    try:
        body = render_to_string('emails/deadline_reminder.txt', context)
        html_body = render_to_string('emails/deadline_reminder.html', context)
    except Exception as t_err:
        logger.error(f"Failed to render deadline reminder template: {t_err}")
        body = f"Hello {student.get_display_name()},\nReminder: deadline for '{project.title}' is on {project.deadline}."
        html_body = None

    link = f"/assignments/{assignment.id}/"
    _create_in_app_notification(
        user=student,
        message=f"Reminder: Deadline for '{project.title}' is in 2 days ({project.deadline.strftime('%b %d')}).",
        link=link
    )

    return send_email(to=student.email, subject=subject, body=body, html_body=html_body)
