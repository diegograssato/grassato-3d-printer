from django.db import models


PLATAFORMA_CHOICES = [
    ('ML', 'MercadoLivre'),
    ('SHOPEE', 'Shopee'),
    ('TIKTOK', 'TikTok Shop'),
]


class Integracao(models.Model):
    plataforma = models.CharField(
        'Plataforma', max_length=20, choices=PLATAFORMA_CHOICES, default='ML'
    )
    nome = models.CharField(
        'Nome / Apelido', max_length=100,
        help_text='Ex.: Minha loja no ML'
    )
    client_id = models.CharField('App ID (Client ID)', max_length=200)
    client_secret = models.CharField(
        'Client Secret', max_length=200,
        help_text='Mantido de forma confidencial — não compartilhe.'
    )
    access_token = models.TextField('Access Token', blank=True)
    refresh_token = models.TextField('Refresh Token', blank=True)
    token_expires_at = models.DateTimeField('Token expira em', null=True, blank=True)
    ml_user_id = models.CharField('Seller ID (ML)', max_length=50, blank=True)
    ativa = models.BooleanField('Ativa', default=True)
    needs_reauth = models.BooleanField(
        'Reautorização necessária', default=False,
        help_text='Marcado automaticamente quando o token expira e não pode ser renovado.'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Integração'
        verbose_name_plural = 'Integrações'
        ordering = ['plataforma', 'nome']

    def __str__(self):
        return f'{self.get_plataforma_display()} — {self.nome}'

    @property
    def autorizada(self):
        return bool(self.access_token) and not self.needs_reauth


class ProdutoIntegracao(models.Model):
    STATUS_CHOICES = [
        ('active', 'Ativo'),
        ('paused', 'Pausado'),
        ('closed', 'Encerrado'),
        ('error', 'Erro'),
    ]

    produto = models.ForeignKey(
        'estoque.Produto', on_delete=models.CASCADE,
        related_name='integracoes', verbose_name='Produto'
    )
    integracao = models.ForeignKey(
        Integracao, on_delete=models.CASCADE,
        related_name='produto_integracoes', verbose_name='Integração'
    )
    sku_externo = models.CharField(
        'ID externo (ex: MLB123456)', max_length=100, blank=True,
        help_text='Preenchido automaticamente após publicação.'
    )
    categoria_ml = models.CharField(
        'Categoria ML (ex: MLB3530)', max_length=50, blank=True,
        help_text='ID da categoria no MercadoLivre. Obrigatório para publicar.'
    )
    picture_urls = models.TextField(
        'URLs das fotos (1 por linha)', blank=True,
        help_text='Informe ao menos 1 URL de foto pública. Obrigatório para anúncios Clássico.'
    )
    ml_attributes_json = models.TextField(
        'Atributos ML (JSON interno)', blank=True,
        help_text='Preenchido automaticamente pelo formulário de publicação.'
    )
    status_externo = models.CharField(
        'Status na plataforma', max_length=20,
        choices=STATUS_CHOICES, default='active'
    )
    sincronizado_em = models.DateTimeField('Sincronizado em', null=True, blank=True)

    class Meta:
        verbose_name = 'Produto na Integração'
        verbose_name_plural = 'Produtos nas Integrações'
        unique_together = [('produto', 'integracao')]

    def __str__(self):
        return f'{self.produto} → {self.integracao} ({self.sku_externo or "sem SKU"})'


def _imagem_upload_path(instance, filename):
    """Salva em integracoes/imagens/<produto_integracao_pk>/<filename>."""
    import os
    ext = os.path.splitext(filename)[1].lower()
    import uuid
    return f'integracoes/imagens/{instance.produto_integracao_id}/{uuid.uuid4().hex}{ext}'


class ImagemProdutoIntegracao(models.Model):
    """Imagens de um anúncio — armazenadas localmente e servidas via URL pública."""

    produto_integracao = models.ForeignKey(
        ProdutoIntegracao, on_delete=models.CASCADE,
        related_name='imagens', verbose_name='Produto-Integração'
    )
    imagem = models.ImageField('Imagem', upload_to=_imagem_upload_path)
    is_capa = models.BooleanField('Capa (1ª foto)', default=False)
    ordem = models.PositiveSmallIntegerField('Ordem', default=0)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Imagem de Anúncio'
        verbose_name_plural = 'Imagens de Anúncio'
        ordering = ['ordem', 'criado_em']

    def __str__(self):
        label = 'capa' if self.is_capa else f'foto {self.ordem}'
        return f'{self.produto_integracao} — {label}'
