from django.db import migrations, models
import django.core.validators
import django.db.models.deletion
from decimal import Decimal


def migrar_filamentos_para_relacional(apps, schema_editor):
    """Copia filamento/peso/comprimento de cada Produto para ProdutoFilamento."""
    Produto = apps.get_model('estoque', 'Produto')
    ProdutoFilamento = apps.get_model('estoque', 'ProdutoFilamento')
    for produto in Produto.objects.select_related('filamento_legado').all():
        if produto.filamento_legado_id:
            ProdutoFilamento.objects.create(
                produto=produto,
                filamento_id=produto.filamento_legado_id,
                peso_filamento_g=produto.peso_filamento_g_legado,
                comprimento_filamento_m=produto.comprimento_filamento_m_legado,
            )


def reverter_filamentos(apps, schema_editor):
    """Restaura campos legados a partir do primeiro ProdutoFilamento."""
    Produto = apps.get_model('estoque', 'Produto')
    ProdutoFilamento = apps.get_model('estoque', 'ProdutoFilamento')
    for produto in Produto.objects.all():
        pf = ProdutoFilamento.objects.filter(produto=produto).first()
        if pf:
            produto.filamento_legado_id = pf.filamento_id
            produto.peso_filamento_g_legado = pf.peso_filamento_g
            produto.comprimento_filamento_m_legado = pf.comprimento_filamento_m
            produto.save(update_fields=[
                'filamento_legado_id',
                'peso_filamento_g_legado',
                'comprimento_filamento_m_legado',
            ])


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0003_fornecedor'),
    ]

    operations = [
        # 1. Renomeia campos legados temporariamente
        migrations.RenameField(
            model_name='produto',
            old_name='filamento',
            new_name='filamento_legado',
        ),
        migrations.RenameField(
            model_name='produto',
            old_name='peso_filamento_g',
            new_name='peso_filamento_g_legado',
        ),
        migrations.RenameField(
            model_name='produto',
            old_name='comprimento_filamento_m',
            new_name='comprimento_filamento_m_legado',
        ),

        # 2. Cria a nova tabela ProdutoFilamento
        migrations.CreateModel(
            name='ProdutoFilamento',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('produto', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='filamentos_produto',
                    to='estoque.produto',
                    verbose_name='Produto',
                )),
                ('filamento', models.ForeignKey(
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='produto_filamentos',
                    to='estoque.filamento',
                    verbose_name='Filamento',
                )),
                ('peso_filamento_g', models.DecimalField(
                    decimal_places=2,
                    help_text='Gramas de filamento por peça',
                    max_digits=8,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                    verbose_name='Peso (g)',
                )),
                ('comprimento_filamento_m', models.DecimalField(
                    decimal_places=2,
                    help_text='Metros de filamento por peça',
                    max_digits=8,
                    validators=[django.core.validators.MinValueValidator(Decimal('0.01'))],
                    verbose_name='Comprimento (m)',
                )),
            ],
            options={
                'verbose_name': 'Filamento do Produto',
                'verbose_name_plural': 'Filamentos do Produto',
                'ordering': ['pk'],
            },
        ),

        # 3. Data migration: copia dados legados para nova tabela
        migrations.RunPython(
            migrar_filamentos_para_relacional,
            reverter_filamentos,
        ),

        # 4. Remove campos legados do Produto
        migrations.RemoveField(
            model_name='produto',
            name='filamento_legado',
        ),
        migrations.RemoveField(
            model_name='produto',
            name='peso_filamento_g_legado',
        ),
        migrations.RemoveField(
            model_name='produto',
            name='comprimento_filamento_m_legado',
        ),
    ]
