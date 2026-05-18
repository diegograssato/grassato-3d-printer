from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('caixa', '0001_initial'),
        ('estoque', '0003_fornecedor'),
    ]

    operations = [
        migrations.AddField(
            model_name='movimentacaocaixa',
            name='fornecedor',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='movimentacoes_caixa',
                to='estoque.fornecedor',
                verbose_name='Fornecedor',
            ),
        ),
    ]
