from django import forms
from .models import Filamento, Produto


class FilamentoForm(forms.ModelForm):
    class Meta:
        model = Filamento
        fields = ['nome', 'cor', 'material', 'peso_total_g', 'peso_disponivel_g', 'preco_por_kg', 'fornecedor']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'cor': forms.TextInput(attrs={'class': 'form-control'}),
            'material': forms.Select(attrs={'class': 'form-select'}),
            'peso_total_g': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'peso_disponivel_g': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'preco_por_kg': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'fornecedor': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['peso_disponivel_g'].required = False
            self.fields['peso_disponivel_g'].help_text = 'Deixe em branco para usar o peso total automaticamente'

    def clean(self):
        cleaned_data = super().clean()
        peso_total = cleaned_data.get('peso_total_g')
        peso_disponivel = cleaned_data.get('peso_disponivel_g')

        if not self.instance.pk and peso_total is not None and not peso_disponivel:
            cleaned_data['peso_disponivel_g'] = peso_total

        if peso_total and peso_disponivel and peso_disponivel > peso_total:
            self.add_error('peso_disponivel_g', 'O peso disponível não pode ser maior que o peso total.')

        return cleaned_data


class ProdutoForm(forms.ModelForm):
    class Meta:
        model = Produto
        fields = [
            'nome', 'descricao', 'filamento', 'peso_filamento_g',
            'comprimento_filamento_m', 'tempo_impressao_horas',
            'preco_custo', 'preco_venda', 'estoque_quantidade',
        ]
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'filamento': forms.Select(attrs={'class': 'form-select'}),
            'peso_filamento_g': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'comprimento_filamento_m': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'tempo_impressao_horas': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'preco_custo': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'preco_venda': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'estoque_quantidade': forms.NumberInput(attrs={'class': 'form-control', 'min': '0'}),
        }
