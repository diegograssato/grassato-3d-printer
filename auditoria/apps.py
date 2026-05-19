import logging

from django.apps import AppConfig
from django.db.models.signals import post_migrate

logger = logging.getLogger(__name__)


def _setup_admin_group(sender, **kwargs):
    """
    Cria o grupo 'Administradores', atribui todas as permissões e adiciona
    o usuário 'admin'. Executado após cada migrate para garantir consistência.
    """
    from django.contrib.auth.models import Group, Permission, User

    group, created = Group.objects.get_or_create(name='Administradores')
    all_perms = Permission.objects.all()
    group.permissions.set(all_perms)

    if created:
        logger.info("Grupo 'Administradores' criado com todas as permissões.")

    try:
        admin_user = User.objects.get(username='admin')
        admin_user.groups.add(group)
        logger.info("Usuário 'admin' adicionado ao grupo 'Administradores'.")
    except User.DoesNotExist:
        pass


class AuditoriaConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'auditoria'
    verbose_name = 'Auditoria'

    def ready(self):
        from .signals import connect_audit_signals
        connect_audit_signals()

        post_migrate.connect(_setup_admin_group, sender=self)
