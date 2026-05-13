from django import forms
from .models import MovimentacaoCaixa


class MovimentacaoCaixaForm(forms.ModelForm):
    class Meta:
        model = MovimentacaoCaixa
        fields = ['data', 'tipo', 'categoria', 'descricao', 'valor']
        widgets = {
            'data': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'tipo': forms.Select(attrs={'class': 'form-select'}),
            'categoria': forms.Select(attrs={'class': 'form-select'}),
            'descricao': forms.TextInput(attrs={'class': 'form-control'}),
            'valor': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }
