def unread_notifications_count(request):
    """
    Exposes unread_notifications_count in all templates for the navbar bell indicator.
    """
    if getattr(request, 'user', None) and request.user.is_authenticated:
        try:
            count = request.user.notifications.filter(is_read=False).count()
            return {'unread_notifications_count': count}
        except Exception:
            return {'unread_notifications_count': 0}
    return {'unread_notifications_count': 0}
