from functools import wraps
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from .models import Role


def get_role(user):
    if not user.is_authenticated:
        return None
    if user.is_superuser:
        return Role.ADMIN
    profile = getattr(user, 'profile', None)
    return profile.role if profile else None


def role_required(*roles):
    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def _wrapped(request, *args, **kwargs):
            role = get_role(request.user)
            if role in roles or request.user.is_superuser:
                return view_func(request, *args, **kwargs)
            messages.error(request, 'You do not have permission to access this page.')
            return redirect('dashboard')
        return _wrapped
    return decorator


admin_required = role_required(Role.ADMIN)
seller_required = role_required(Role.ADMIN, Role.SELLER)
customer_required = role_required(Role.ADMIN, Role.CUSTOMER)
