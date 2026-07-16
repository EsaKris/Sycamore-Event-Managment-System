"""
Public API root, mounted at /api/v1/ (see config/urls.py). Each app owns
its own serializers.py + api_views.py, exactly like every other
app-owned resource in this project (dashboard views, forms, urls) — no
separate 'api app'. This file only aggregates routes.

Authentication: token-based (POST /api/v1/auth/token/ with username +
password). All other endpoints require `Authorization: Token <key>` and
an active administrator account — the same population who can use the
dashboard, since attendees never get accounts (see apps.accounts).
"""

from rest_framework.routers import DefaultRouter

from apps.accounts.api import obtain_token
from apps.attendance.api_views import AttendanceSessionViewSet, AttendanceViewSet
from apps.departments.api_views import DepartmentViewSet
from apps.events.api_views import EventViewSet
from apps.people.api_views import PersonViewSet
from apps.registrations.api_views import RegistrationViewSet
from django.urls import include, path

router = DefaultRouter()
router.register('events', EventViewSet, basename='event')
router.register('departments', DepartmentViewSet, basename='department')
router.register('people', PersonViewSet, basename='person')
router.register('registrations', RegistrationViewSet, basename='registration')
router.register('attendance-sessions', AttendanceSessionViewSet, basename='attendance-session')
router.register('attendance', AttendanceViewSet, basename='attendance')

urlpatterns = [
    path('auth/token/', obtain_token, name='api_obtain_token'),
    path('', include(router.urls)),
]
