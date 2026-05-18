from django.db import migrations, models
import django.db.models.deletion


def migrar_fornecedores(apps, schema_editor):
    """Converte strings de fornecedor existentes em objetos Fornecedor."""
    Filamento = apps.get_model('estoque', 'Filamento')
    Fornecedor = apps.get_model('estoque', 'Fornecedor')
    fornecedores_cache = {}
    for filamento in Filamento.objects.exclude(fornecedor_str='').exclude(fornecedor_str__isnull=True):
        nome = filamento.fornecedor_str.strip()
        if not nome:
            continue
        if nome not in fornecedores_cache:
            fornecedores_cache[nome] = Fornecedor.objects.create(nome=nome)
        filamento.fornecedor_fk = fornecedores_cache[nome]
        filamento.save(update_fields=['fornecedor_fk'])


def reverter_fornecedores(apps, schema_editor):
    """Reverte FKs de volta para strings."""
    Filamento = apps.get_model('estoque', 'Filamento')
    for filamento in Filamento.objects.filter(fornecedor_fk__isnull=False):
        filamento.fornecedor_str = filamento.fornecedor_fk.nome
        filamento.save(update_fields=['fornecedor_str'])


class Migration(migrations.Migration):

    dependencies = [
        ('estoque', '0002_produto_sku'),
    ]

    operations = [
        # 1. Cria model Fornecedor
        migrations.CreateModel(
            name='Fornecedor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('nome', models.CharField(max_length=150, verbose_name='Nome')),
                ('telefone', models.CharField(blank=True, max_length=20, verbose_name='Telefone')),
                ('email', models.EmailField(blank=True, verbose_name='E-mail')),
                ('site', models.URLField(blank=True, verbose_name='Site')),
                ('observacoes', models.TextField(blank=True, verbose_name='Observações')),
                ('criado_em', models.DateTimeField(auto_now_add=True)),
            ],
            options={
                'verbose_name': 'Fornecedor',
                'verbose_name_plural': 'Fornecedores',
                'ordering': ['nome'],
            },
        ),
        # 2. Renomeia CharField existente para fornecedor_str (temporário)
        migrations.RenameField(
            model_name='filamento',
            old_name='fornecedor',
            new_name='fornecedor_str',
        ),
        # 3. Adiciona FK temporária fornecedor_fk
        migrations.AddField(
            model_name='filamento',
            name='fornecedor_fk',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='filamentos',
                to='estoque.fornecedor',
                verbose_name='Fornecedor',
            ),
        ),
        # 4. Migra dados de fornecedor_str → Fornecedor + fornecedor_fk
        migrations.RunPython(migrar_fornecedores, reverter_fornecedores),
        # 5. Remove CharField antigo
        migrations.RemoveField(
            model_name='filamento',
            name='fornecedor_str',
        ),
        # 6. Renomeia FK para o nome definitivo
        migrations.RenameField(
            model_name='filamento',
            old_name='fornecedor_fk',
            new_name='fornecedor',
        ),
    ]
