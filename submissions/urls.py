from django.urls import path

from . import views

app_name = "submissions"

urlpatterns = [
    path("", views.teacher_submissions_list_view, name="submission_list"),
    path("upload/", views.student_upload_picker_view, name="upload_picker"),
    path("upload/<int:assignment_id>/", views.upload_submission_view, name="upload_submission"),
    path("<int:submission_id>/", views.teacher_submission_detail_view, name="submission_detail"),
    path("<int:submission_id>/download/", views.download_submission_view, name="download_submission"),
]
