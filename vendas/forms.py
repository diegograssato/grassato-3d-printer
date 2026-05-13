from django import forms
from .models import Venda


class VendaForm(forms.ModelForm):
    class Meta:
        model = Venda
        fields = ['data', 'produto', 'quantidade', 'preco_unitario', 'forma_pagamento', 'observacoes']
        widgets = {
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'produto': forms.Select(attrs={'class': 'form-select', 'id': 'id_produto'}),
            'quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'id': 'id_quantidade'}),
            'preco_unitario': forms.NumberInput(attrs={
                'class': 'form-control', 'step': '0.01', 'min': '0.01', 'id': 'id_preco_unitario'
            }),
            'forma_pagamento': forms.Select(attrs={'class': 'form-select'}),
            'observacoes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from estoque.models import Produto
        self.fields['produto'].queryset = Produto.objects.filter(ativo=True).select_related('filamento')
