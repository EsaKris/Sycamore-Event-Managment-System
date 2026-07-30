class AuditLogMiddleware:
    """
    Attaches the request's IP address to the request object so any view
    or service can write it into an AuditLog entry without re-deriving it.

    The actual logging happens at the point of action across the codebase
    (service-layer methods in accounts/, events/, departments/, followup/,
    registrations/ services.py and views.py, plus the login view in
    apps/dashboard/views.py) rather than here — this middleware only
    supplies the IP address, consistently, to whichever of those write
    paths the request ends up on.
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
