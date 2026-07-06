from .models import CorrectionRequest


def user_role(request):
    base = {'is_app_admin': False, 'is_checker': False, 'is_teacher': False, 'pending_copy_requests_count': 0}
    if not request.user.is_authenticated:
        return base
    profile = getattr(request.user, 'checker_profile', None)
    is_admin = request.user.is_superuser or bool(profile and profile.role == 'admin')
    pending_count = 0
    if is_admin:
        pending_count = CorrectionRequest.objects.filter(status=CorrectionRequest.STATUS_PENDING).count()
    if not profile:
        return {**base, 'is_app_admin': request.user.is_superuser, 'pending_copy_requests_count': pending_count}
    return {
        'is_app_admin': is_admin,
        'is_checker': profile.role == 'checker',
        'is_teacher': profile.role == 'teacher',
        'current_profile': profile,
        'pending_copy_requests_count': pending_count,
    }
