from django import forms
from .models import Integracao, ProdutoIntegracao


class MultipleFileInput(forms.FileInput):
    """Widget que suporta seleção de múltiplos arquivos."""
    allow_multiple_selected = True

    def value_from_datadict(self, data, files, name):
        """Retorna todos os arquivos enviados, não apenas o primeiro."""
        if hasattr(files, 'getlist'):
            return files.getlist(name)
        return files.get(name)


class MultipleFileField(forms.FileField):
    """Campo que devolve uma lista de arquivos ao invés de um único arquivo."""

    def __init__(self, *args, **kwargs):
        kwargs.setdefault('widget', MultipleFileInput())
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        single = super().clean
        if isinstance(data, (list, tuple)):
            return [single(d, initial) for d in data]
        return [single(data, initial)]


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
    # Upload múltiplo — mínimo 2 imagens (capa + 1 normal)
    imagens = MultipleFileField(
        label='Fotos do anúncio',
        required=True,
        widget=MultipleFileInput(attrs={
            'class': 'd-none',
            'id': 'id_imagens',
            'accept': 'image/jpeg,image/png,image/webp',
        }),
        help_text='Mínimo 2 fotos. A primeira será a capa do anúncio.',
    )

    class Meta:
        model = ProdutoIntegracao
        fields = ['integracao', 'categoria_ml']
        widgets = {
            'integracao': forms.Select(attrs={'class': 'form-select'}),
            'categoria_ml': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Ex.: MLB3530 — Impressoras 3D',
                'id': 'id_categoria_ml',
            }),
        }

    def __init__(self, *args, produto=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.produto = produto
        self.fields['integracao'].queryset = Integracao.objects.filter(ativa=True)
        if produto:
            linked_ids = ProdutoIntegracao.objects.filter(
                produto=produto
            ).values_list('integracao_id', flat=True)
            self.fields['integracao'].queryset = self.fields['integracao'].queryset.exclude(
                id__in=linked_ids
            )

    def clean_imagens(self):
        """
        Valida as imagens conforme requisitos do MercadoLivre:
        - Mínimo 2, máximo 10 fotos
        - Formatos: JPEG, PNG, WEBP
        - Tamanho: até 10 MB por arquivo
        - Dimensão mínima: 500px no lado maior (verificado com Pillow)
        """
        from PIL import Image, UnidentifiedImageError

        ALLOWED_MIME = {'image/jpeg', 'image/png', 'image/webp'}
        MAX_FILES = 10
        MAX_BYTES = 10 * 1024 * 1024
        MIN_PX = 500

        files = self.cleaned_data.get('imagens') or []
        if not isinstance(files, list):
            files = [files]

        if len(files) < 2:
            raise forms.ValidationError(
                'Envie pelo menos 2 fotos: uma de capa e uma adicional.'
            )
        if len(files) > MAX_FILES:
            raise forms.ValidationError(
                f'Envie no máximo {MAX_FILES} fotos.'
            )

        for f in files:
            if f.content_type not in ALLOWED_MIME:
                raise forms.ValidationError(
                    f'"{f.name}": formato inválido. Use JPG, PNG ou WEBP.'
                )
            if f.size > MAX_BYTES:
                raise forms.ValidationError(
                    f'"{f.name}" excede o limite de 10 MB ({f.size // (1024*1024)} MB).'
                )
            # Verifica dimensão mínima com Pillow
            try:
                f.seek(0)
                img = Image.open(f)
                img.verify()          # detecta arquivos corrompidos
                f.seek(0)
                img = Image.open(f)   # reabre após verify (que consome o stream)
                w, h = img.size
                if max(w, h) < MIN_PX:
                    raise forms.ValidationError(
                        f'"{f.name}" é muito pequena ({w}×{h}px). '
                        f'O lado maior precisa ter no mínimo {MIN_PX}px.'
                    )
            except forms.ValidationError:
                raise
            except UnidentifiedImageError:
                raise forms.ValidationError(
                    f'"{f.name}" não é uma imagem válida.'
                )
            except Exception as exc:
                raise forms.ValidationError(
                    f'"{f.name}": erro ao verificar imagem — {exc}'
                )
            finally:
                try:
                    f.seek(0)
                except Exception:
                    pass

        return files
