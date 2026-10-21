from django.urls import path

from . import views

app_name = "dashboard"

urlpatterns = [
    path("", views.home_view, name="home"),
    path("dashboard/", views.dashboard_view, name="dashboard"),
    path("notifications/", views.notifications_list_view, name="notifications_list"),
    path("notifications/<int:notification_id>/read/", views.mark_notification_read_view, name="mark_notification_read"),
    path("notifications/read-all/", views.mark_all_notifications_read_view, name="mark_all_notifications_read"),
]
