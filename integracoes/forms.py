from django import forms
from .models import Integracao, ProdutoIntegracao


class IntegracaoForm(forms.ModelForm):
    class Meta:
        model = Integracao
        fields = ['plataforma', 'nome', 'client_id', 'client_secret', 'ativa']
        widgets = {
            'plataforma': forms.Select(attrs={'class': 'form-select'}),
            'nome': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Ex.: Minha loja no ML'}),
            'client_id': forms.TextInput(attrs={'class': 'form-control'}),
            'client_secret': forms.PasswordInput(
                attrs={'class': 'form-control'},
                render_value=True,
            ),
            'ativa': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'client_secret': 'O secret é armazenado de forma segura e nunca exibido após salvo.',
        }


class ProdutoIntegracaoForm(forms.ModelForm):
    class Meta:
        model = ProdutoIntegracao
        fields = ['integracao', 'categoria_ml', 'picture_urls']
        widgets = {
            'integracao': forms.Select(attrs={'class': 'form-select'}),
            'categoria_ml': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: MLB3530 — Impressoras 3D',
                'id': 'id_categoria_ml',
            }),
            'picture_urls': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'https://exemplo.com/foto1.jpg\nhttps://exemplo.com/foto2.jpg',
                'id': 'id_picture_urls',
            }),
        }
        help_texts = {
            'picture_urls': 'Uma URL por linha. Obrigatório para anúncios Clássico (gold_special).',
        }

    def __init__(self, *args, produto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.produto = produto
        # Limit to authorized ML integrations
        self.fields['integracao'].queryset = Integracao.objects.filter(ativa=True)
        # Exclude integrations already linked to this product
        if produto:
            linked_ids = ProdutoIntegracao.objects.filter(
                produto=produto
            ).values_list('integracao_id', flat=True)
            self.fields['integracao'].queryset = self.fields['integracao'].queryset.exclude(
                id__in=linked_ids
            )
