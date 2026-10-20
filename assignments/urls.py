from django.urls import path
from . import views

app_name = 'assignments'

urlpatterns = [
    path('', views.assign_project_select_view, name='assign_project_select'),
    path('assign/<int:project_id>/', views.assign_students_view, name='assign_students'),
    path('my/', views.my_assignments_view, name='my_assignments'),
    path('<int:pk>/', views.assignment_detail_view, name='assignment_detail'),
]
