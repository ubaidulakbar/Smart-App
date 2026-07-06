from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect


def is_app_admin(user):
    if user.is_superuser:
        return True
    profile = getattr(user, 'checker_profile', None)
    return bool(profile and profile.role == 'admin')


def is_checker_user(user):
    profile = getattr(user, 'checker_profile', None)
    return bool(profile and profile.role == 'checker' and profile.is_active_checker and user.is_active)


def is_teacher_user(user):
    profile = getattr(user, 'checker_profile', None)
    return bool(profile and profile.role == 'teacher' and profile.is_active_checker and user.is_active)


def app_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if not is_app_admin(request.user):
            messages.error(request, 'Admin access is required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def checker_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if is_app_admin(request.user):
            messages.info(request, 'Admin users cannot lock notebook-checking records. Use a checker login for checking.')
            return redirect('dashboard')
        if not is_checker_user(request.user):
            messages.error(request, 'Checker access is required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper


def teacher_required(view_func):
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if is_app_admin(request.user):
            messages.info(request, 'Admin users cannot enter teacher course progress. Use a teacher login for progress entry.')
            return redirect('dashboard')
        if not is_teacher_user(request.user):
            messages.error(request, 'Teacher access is required.')
            return redirect('dashboard')
        return view_func(request, *args, **kwargs)
    return wrapper
