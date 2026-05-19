from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    ACAO_CRIADO = 'CRIADO'
    ACAO_ATUALIZADO = 'ATUALIZADO'
    ACAO_EXCLUIDO = 'EXCLUIDO'

    ACAO_CHOICES = [
        (ACAO_CRIADO, 'Criado'),
        (ACAO_ATUALIZADO, 'Atualizado'),
        (ACAO_EXCLUIDO, 'Excluído'),
    ]

    PLATAFORMA_CHOICES = [
        ('', 'Manual'),
        ('ML', 'MercadoLivre'),
        ('SHOPEE', 'Shopee'),
        ('TIKTOK', 'TikTok Shop'),
    ]

    timestamp = models.DateTimeField('Data/hora', auto_now_add=True, db_index=True)
    acao = models.CharField('Ação', max_length=20, choices=ACAO_CHOICES, db_index=True)
    modelo = models.CharField('Modelo', max_length=100, db_index=True)
    objeto_id = models.CharField('ID do objeto', max_length=50)
    objeto_repr = models.TextField('Representação')
    usuario_nome = models.CharField('Usuário / Origem', max_length=150, db_index=True)
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        verbose_name='Usuário',
        related_name='audit_logs',
    )
    plataforma = models.CharField(
        'Plataforma',
        max_length=20,
        blank=True,
        choices=PLATAFORMA_CHOICES,
    )
    changes = models.JSONField('Alterações', default=dict, blank=True)
    event_json = models.JSONField('JSON do evento', null=True, blank=True)

    class Meta:
        verbose_name = 'Log de Auditoria'
        verbose_name_plural = 'Logs de Auditoria'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['modelo', 'objeto_id']),
        ]

    def __str__(self):
        ts = self.timestamp.strftime('%d/%m/%Y %H:%M') if self.timestamp else '?'
        return f'[{ts}] {self.acao} — {self.modelo} #{self.objeto_id} por {self.usuario_nome}'

    @property
    def plataforma_label(self):
        mapping = {'ML': 'MercadoLivre', 'SHOPEE': 'Shopee', 'TIKTOK': 'TikTok Shop'}
        return mapping.get(self.plataforma, 'Manual' if not self.plataforma else self.plataforma)

    @property
    def acao_badge_class(self):
        return {
            self.ACAO_CRIADO: 'success',
            self.ACAO_ATUALIZADO: 'warning',
            self.ACAO_EXCLUIDO: 'danger',
        }.get(self.acao, 'secondary')
