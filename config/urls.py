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
from django.contrib.sitemaps.views import sitemap
from django.http import HttpResponse
from django.urls import include, path

from apps.core.sitemaps import EventRegisterSitemap, StaticViewSitemap
from apps.registrations import public_views

admin.site.site_header = 'Sycamore System Administration (Dev/Maintenance)'
admin.site.site_title = 'Esa Admin'

sitemaps = {
    'static': StaticViewSitemap,
    'events': EventRegisterSitemap,
}


def robots_txt(request):
    """Points crawlers at the sitemap and keeps the whole public site
    crawlable — nothing here is sensitive; the actual dashboard/admin
    areas are protected by login, not by asking robots nicely to skip
    them (security through obscurity isn't security)."""
    lines = [
        'User-agent: *',
        'Allow: /',
        f'Sitemap: {request.scheme}://{request.get_host()}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain')


urlpatterns = [
    path('sys-admin/', admin.site.urls),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap'),
    path('robots.txt', robots_txt, name='robots_txt'),
    # The marketing/landing page — resolves the same SystemSettings.default_event
    # as the short '/register/' URL, so "which event is live right now" only
    # has to be set in one place (Settings → Default event for public site).
    path('', public_views.landing, name='landing'),
    path('register/', include('apps.registrations.public_urls')),
    path('dashboard/', include('apps.dashboard.urls')),
    path('dashboard/registrations/', include('apps.registrations.urls')),
    path('dashboard/attendance/', include('apps.attendance.urls')),
    path('dashboard/people/', include('apps.people.urls')),
    path('dashboard/followup/', include('apps.followup.urls')),
    path('dashboard/campaigns/', include('apps.campaigns.urls')),
    path('dashboard/administrators/', include('apps.accounts.urls')),
    path('dashboard/departments/', include('apps.departments.urls')),
    path('dashboard/events/', include('apps.events.urls')),
    path('api/v1/', include('config.api_urls')),
    path('api-auth/', include('rest_framework.urls')),
]

if settings.DEBUG or settings.SERVE_MEDIA_VIA_DJANGO:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
