"""
XML sitemap for the public site (Google Search Console → Submit sitemap).

Deliberately NOT using django.contrib.sites — these Sitemap subclasses
return path-only locations, and django.contrib.sitemaps.views.sitemap
builds full URLs from the incoming request when the sites framework isn't
installed. That avoids needing a Site row (and its own migration/config)
just to know our own domain, which the request already tells us anyway.

Only public, unauthenticated pages belong here — nothing under /dashboard/.
"""

from django.contrib.sitemaps import Sitemap
from django.urls import reverse

from apps.events.models import Event, RegistrationStatus


class StaticViewSitemap(Sitemap):
    protocol = None  # inferred from the request
    changefreq = 'weekly'
    priority = 1.0

    def items(self):
        return ['landing']

    def location(self, item):
        return reverse(item)


class EventRegisterSitemap(Sitemap):
    """One entry per event currently open for public registration —
    exactly the pages worth a search engine crawling and indexing."""
    protocol = None
    changefreq = 'daily'
    priority = 0.9

    def items(self):
        return Event.objects.filter(registration_status=RegistrationStatus.OPEN).order_by('-year')

    def location(self, event):
        return reverse('public:register', kwargs={'event_slug': event.slug})

    def lastmod(self, event):
        return event.updated_at
