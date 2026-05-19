def admin_group(request):
    """
    Injeta `is_admin_group` no contexto de todos os templates.
    True quando o usuário é superusuário ou pertence ao grupo 'Administradores'.
    """
    if not hasattr(request, 'user') or not request.user.is_authenticated:
        return {'is_admin_group': False}

    is_admin = (
        request.user.is_superuser
        or request.user.groups.filter(name='Administradores').exists()
    )
    return {'is_admin_group': is_admin}
