from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal


class Fornecedor(models.Model):
    nome = models.CharField('Nome', max_length=150)
    telefone = models.CharField('Telefone', max_length=20, blank=True)
    email = models.EmailField('E-mail', blank=True)
    site = models.URLField('Site', blank=True)
    observacoes = models.TextField('Observações', blank=True)
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Fornecedor'
        verbose_name_plural = 'Fornecedores'
        ordering = ['nome']

    def __str__(self):
        return self.nome


MATERIAL_CHOICES = [
    ('PLA', 'PLA'),
    ('ABS', 'ABS'),
    ('PETG', 'PETG'),
    ('TPU', 'TPU'),
    ('ASA', 'ASA'),
    ('NYLON', 'Nylon'),
    ('RESIN', 'Resina'),
    ('OUTRO', 'Outro'),
]


class Filamento(models.Model):
    nome = models.CharField('Nome/Marca', max_length=100)
    cor = models.CharField('Cor', max_length=50)
    material = models.CharField('Material', max_length=20, choices=MATERIAL_CHOICES, default='PLA')
    peso_total_g = models.DecimalField(
        'Peso total (g)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Peso total do carretel em gramas (ex: 1000g = 1kg)'
    )
    peso_disponivel_g = models.DecimalField(
        'Peso disponível (g)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Peso atual disponível. Preenchido automaticamente na criação.'
    )
    preco_por_kg = models.DecimalField(
        'Preço por kg (R$)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    fornecedor = models.ForeignKey(
        'Fornecedor', on_delete=models.SET_NULL,
        null=True, blank=True,
        verbose_name='Fornecedor',
        related_name='filamentos',
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Filamento'
        verbose_name_plural = 'Filamentos'
        ordering = ['material', 'cor']

    def __str__(self):
        return f'{self.material} {self.cor} — {self.nome}'

    @property
    def percentual_disponivel(self):
        if not self.peso_total_g:
            return Decimal('0')
        return (self.peso_disponivel_g / self.peso_total_g * 100).quantize(Decimal('0.1'))

    @property
    def preco_por_grama(self):
        return self.preco_por_kg / Decimal('1000')

    @property
    def status_estoque(self):
        pct = float(self.percentual_disponivel)
        if pct <= 10:
            return ('danger', 'Crítico')
        elif pct <= 30:
            return ('warning', 'Baixo')
        return ('success', 'OK')


class Produto(models.Model):
    nome = models.CharField('Nome', max_length=150)
    descricao = models.TextField('Descrição', blank=True)
    tempo_impressao_horas = models.DecimalField(
        'Tempo de impressão (h)', max_digits=6, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    preco_custo = models.DecimalField(
        'Preço de custo (R$)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0'))],
        help_text='Custo total de produção (filamento + energia + outros)'
    )
    preco_venda = models.DecimalField(
        'Preço de venda (R$)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    estoque_quantidade = models.IntegerField(
        'Estoque', default=0,
        validators=[MinValueValidator(0)],
        help_text='Quantidade de unidades em estoque'
    )
    ativo = models.BooleanField('Ativo', default=True)
    sku = models.CharField(
        'SKU', max_length=20, unique=True, blank=True, editable=False,
        help_text='Gerado automaticamente no cadastro. Ex.: 3D-00001'
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Produto'
        verbose_name_plural = 'Produtos'
        ordering = ['nome']

    def __str__(self):
        return self.nome

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if not self.sku:
            # Gera SKU após ter o PK (primeiro save)
            self.sku = f'3D-{self.pk:05d}'
            type(self).objects.filter(pk=self.pk).update(sku=self.sku)

    @property
    def margem_lucro_pct(self):
        if not self.preco_custo:
            return Decimal('0')
        return ((self.preco_venda - self.preco_custo) / self.preco_custo * 100).quantize(Decimal('0.1'))

    @property
    def custo_filamento(self):
        return sum(
            pf.filamento.preco_por_grama * pf.peso_filamento_g
            for pf in self.filamentos_produto.select_related('filamento').all()
        )

    @property
    def filamento_principal(self):
        """Retorna o primeiro filamento cadastrado (compatibilidade)."""
        pf = self.filamentos_produto.select_related('filamento').first()
        return pf.filamento if pf else None

    @property
    def peso_filamento_total_g(self):
        """Soma de gramas de todos os filamentos por peça."""
        return sum(
            pf.peso_filamento_g for pf in self.filamentos_produto.all()
        ) or Decimal('0')


class ProdutoFilamento(models.Model):
    produto = models.ForeignKey(
        Produto, on_delete=models.CASCADE,
        related_name='filamentos_produto',
        verbose_name='Produto',
    )
    filamento = models.ForeignKey(
        Filamento, on_delete=models.PROTECT,
        related_name='produto_filamentos',
        verbose_name='Filamento',
    )
    peso_filamento_g = models.DecimalField(
        'Peso (g)', max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Gramas de filamento por peça',
    )
    comprimento_filamento_m = models.DecimalField(
        'Comprimento (m)', max_digits=8, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text='Metros de filamento por peça',
    )

    class Meta:
        verbose_name = 'Filamento do Produto'
        verbose_name_plural = 'Filamentos do Produto'
        ordering = ['pk']

    def __str__(self):
        return f'{self.filamento} — {self.peso_filamento_g}g'
