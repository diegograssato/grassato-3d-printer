from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def admin_group_required(view_func):
    """
    Decorator que exige que o usuário pertença ao grupo 'Administradores'
    ou seja superusuário. Redireciona para login se não autenticado.
    """
    @login_required
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        if (
            request.user.is_superuser
            or request.user.groups.filter(name='Administradores').exists()
        ):
            return view_func(request, *args, **kwargs)
        raise PermissionDenied

    return wrapper
