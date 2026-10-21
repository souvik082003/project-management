from django.urls import path

from . import views

app_name = "reviews"

urlpatterns = [
    # Teacher endpoints
    path("", views.reviews_dashboard_view, name="reviews_dashboard"),
    path("submission/<int:submission_id>/", views.give_feedback_view, name="submission_review"),
    path("submission/<int:submission_id>/feedback/", views.give_feedback_view, name="give_feedback"),
    path("assignment/<int:assignment_id>/marks/", views.assign_marks_view, name="assign_marks"),
    path("project/<int:project_id>/report/", views.marks_report_view, name="marks_report"),
    path("project/<int:project_id>/report/csv/", views.marks_report_csv_view, name="marks_report_csv"),
    # Student endpoints
    path("feedback/", views.student_feedback_list_view, name="student_feedback_list"),
    path(
        "assignment/<int:assignment_id>/feedback/",
        views.student_assignment_feedback_view,
        name="student_assignment_feedback",
    ),
    path("marks/", views.student_marks_list_view, name="student_marks_list"),
    path("assignment/<int:assignment_id>/marks/view/", views.student_view_marks_view, name="student_view_marks"),
]
