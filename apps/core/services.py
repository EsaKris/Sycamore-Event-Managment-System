"""
Notification creation. Called explicitly from service-layer code at the
points the spec names — New Registration, New Administrator, Email
Failed, Upcoming Event — the same convention already used for AuditLog:
explicit calls at the point of action, not signals, so the trigger is
traceable by reading the calling code.
"""

from .models import Notification, NotificationLevel


class NotificationService:

    @staticmethod
    def notify(*, title: str, message: str = '', level: str = NotificationLevel.INFO, link_url: str = '') -> Notification:
        return Notification.objects.create(title=title, message=message, level=level, link_url=link_url)

    @staticmethod
    def unread_count(user) -> int:
        if not getattr(user, 'is_authenticated', False):
            return 0
        return Notification.objects.exclude(read_by=user).count()

    @staticmethod
    def unread_for(user, limit=8):
        if not getattr(user, 'is_authenticated', False):
            return Notification.objects.none()
        return Notification.objects.exclude(read_by=user)[:limit]

    @staticmethod
    def mark_read(notification: Notification, user):
        notification.read_by.add(user)

    @staticmethod
    def mark_all_read(user):
        for n in Notification.objects.exclude(read_by=user):
            n.read_by.add(user)
