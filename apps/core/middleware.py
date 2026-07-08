class AuditLogMiddleware:
    """
    Attaches the request's IP address to the request object so any view
    or service can write it into an AuditLog entry without re-deriving it.

    This is intentionally minimal for now. The full Activity Logs module
    (auto-logging every create/update/delete with affected-record links)
    is a later phase — see apps/core/models.py:AuditLog.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.client_ip = self._get_client_ip(request)
        return self.get_response(request)

    @staticmethod
    def _get_client_ip(request):
        forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if forwarded_for:
            return forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR')
