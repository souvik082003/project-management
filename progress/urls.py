from django.urls import path
from . import views

app_name = 'progress'

urlpatterns = [
    path('update/', views.student_progress_list_view, name='student_progress_list'),
    path('update/<int:assignment_id>/', views.update_progress_view, name='update_progress'),
    path('monitor/', views.monitor_progress_view, name='monitor_progress'),
    path('history/<int:assignment_id>/', views.assignment_progress_history_view, name='assignment_progress_history'),
    path('report/', views.progress_report_select_view, name='progress_report_select'),
    path('report/<int:project_id>/', views.progress_report_view, name='progress_report'),
    path('report/<int:project_id>/csv/', views.progress_report_csv_view, name='progress_report_csv'),
]
