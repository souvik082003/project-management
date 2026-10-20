"""
URL configuration for pms project.
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('dashboard.urls', namespace='dashboard')),
    path('accounts/', include('accounts.urls', namespace='accounts')),
    path('projects/', include('projects.urls', namespace='projects')),
    path('assignments/', include('assignments.urls', namespace='assignments')),
    path('progress/', include('progress.urls', namespace='progress')),
    path('submissions/', include('submissions.urls', namespace='submissions')),
    path('reviews/', include('reviews.urls', namespace='reviews')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
