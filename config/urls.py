"""
Root URL configuration.

Per spec, Django Admin is NOT the primary interface — it's kept available
only for development/maintenance, at a non-default path so it isn't
discoverable by attendees. The real, custom SaaS-style dashboard
(apps.dashboard or similar) is a later phase; '/dashboard/' is reserved
for it so LOGIN_URL / LOGIN_REDIRECT_URL in settings.py don't need to
change when it's built.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

admin.site.site_header = 'SEMS System Administration (Dev/Maintenance)'
admin.site.site_title = 'SEMS Admin'

urlpatterns = [
    path('sys-admin/', admin.site.urls),
    path('dashboard/', include('apps.dashboard.urls')),  # phase 2
    # path('api/v1/', include('config.api_urls')),          # phase: API module
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
