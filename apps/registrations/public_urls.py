from django.urls import path

from . import public_views

app_name = 'public'

urlpatterns = [
    # Literal paths first — 'check-returning' and '' would otherwise be
    # swallowed by the <slug:event_slug> catch-all below, since a bare
    # segment is a syntactically valid slug.
    path('', public_views.public_register_default, name='register_default'),
    path('check-returning/', public_views.check_returning, name='check_returning'),

    path('<slug:event_slug>/', public_views.public_register, name='register'),
    path('<slug:event_slug>/success/', public_views.public_register_success, name='success'),
]

