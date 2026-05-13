from django.db import models
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.utils import timezone


class MovimentacaoCaixa(models.Model):
    TIPO = [
        ('ENTRADA', 'Entrada'),
        ('SAIDA', 'Saída'),
    ]

    CATEGORIA = [
        ('VENDA', 'Venda'),
        ('FILAMENTO', 'Compra de Filamento'),
        ('EQUIPAMENTO', 'Equipamento'),
        ('MANUTENCAO', 'Manutenção'),
        ('ENERGIA', 'Energia Elétrica'),
        ('OUTROS_CUSTO', 'Outros Custos'),
        ('OUTROS_RECEITA', 'Outras Receitas'),
    ]

    data = models.DateField('Data', default=timezone.now)
    tipo = models.CharField('Tipo', max_length=10, choices=TIPO)
    categoria = models.CharField('Categoria', max_length=20, choices=CATEGORIA)
    descricao = models.CharField('Descrição', max_length=255)
    valor = models.DecimalField(
        'Valor (R$)', max_digits=10, decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    venda = models.OneToOneField(
        'vendas.Venda', on_delete=models.CASCADE,
        null=True, blank=True,
        related_name='movimentacao_caixa',
        verbose_name='Venda origem'
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimentação de Caixa'
        verbose_name_plural = 'Movimentações de Caixa'
        ordering = ['-data', '-criado_em']

    def __str__(self):
        return f'{self.get_tipo_display()} — {self.descricao} — R$ {self.valor:.2f}'
