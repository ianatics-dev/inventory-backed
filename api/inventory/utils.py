# utils.py
from quickstart.models import ActivityLog


def get_client_ip(request):
    x_forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR")
    if x_forwarded_for:
        return x_forwarded_for.split(",")[0]
    return request.META.get("REMOTE_ADDR")


def log_activity(
    request,
    action,
    module,
    description,
    target_id=None,
    target_name=None,
):
    user = request.user if request.user.is_authenticated else None
    role = None
    if user and hasattr(user, "profile"):
        role = getattr(user.profile, "role", None)

    ActivityLog.objects.create(
        user=user,
        username=user.username if user else "Anonymous",
        role=role,
        action=action,
        module=module,
        description=description,
        target_id=str(target_id) if target_id is not None else None,
        target_name=target_name,
        ip_address=get_client_ip(request),
        user_agent=request.META.get("HTTP_USER_AGENT", ""),
    )