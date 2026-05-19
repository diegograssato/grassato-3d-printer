import csv
import io
import zipfile
from decimal import Decimal, InvalidOperation

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render

from auditoria.decorators import admin_group_required
from estoque.models import Filamento, Fornecedor, Produto

# ──────────────────────────────────────────────
# Definição dos cabeçalhos de cada tipo de CSV
# ──────────────────────────────────────────────
FORNECEDOR_HEADERS = ['nome', 'telefone', 'email', 'site', 'observacoes']
FILAMENTO_HEADERS = [
    'nome', 'cor', 'material',
    'peso_total_g', 'peso_disponivel_g', 'preco_por_kg',
    'fornecedor_nome',
]
PRODUTO_HEADERS = [
    'nome', 'descricao',
    'filamento_nome', 'filamento_cor', 'filamento_material',
    'peso_filamento_g', 'comprimento_filamento_m', 'tempo_impressao_horas',
    'preco_custo', 'preco_venda', 'estoque_quantidade', 'ativo',
]


# ──────────────────────────────────────────────
# Detecção automática de tipo pelo cabeçalho
# ──────────────────────────────────────────────
def _detect_type(fieldnames):
    if fieldnames is None:
        return None
    headers = {h.strip() for h in fieldnames}
    if headers == set(FORNECEDOR_HEADERS):
        return 'fornecedor'
    if headers == set(FILAMENTO_HEADERS):
        return 'filamento'
    if headers == set(PRODUTO_HEADERS):
        return 'produto'
    return None


# ──────────────────────────────────────────────
# Exportação
# ──────────────────────────────────────────────
def _export_fornecedores():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FORNECEDOR_HEADERS)
    writer.writeheader()
    for f in Fornecedor.objects.all().order_by('nome'):
        writer.writerow({
            'nome': f.nome,
            'telefone': f.telefone,
            'email': f.email,
            'site': f.site,
            'observacoes': f.observacoes,
        })
    return output.getvalue()


def _export_filamentos():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=FILAMENTO_HEADERS)
    writer.writeheader()
    for f in Filamento.objects.select_related('fornecedor').order_by('material', 'cor'):
        writer.writerow({
            'nome': f.nome,
            'cor': f.cor,
            'material': f.material,
            'peso_total_g': str(f.peso_total_g),
            'peso_disponivel_g': str(f.peso_disponivel_g),
            'preco_por_kg': str(f.preco_por_kg),
            'fornecedor_nome': f.fornecedor.nome if f.fornecedor else '',
        })
    return output.getvalue()


def _export_produtos():
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=PRODUTO_HEADERS)
    writer.writeheader()
    for p in Produto.objects.select_related('filamento__fornecedor').order_by('nome'):
        writer.writerow({
            'nome': p.nome,
            'descricao': p.descricao,
            'filamento_nome': p.filamento.nome,
            'filamento_cor': p.filamento.cor,
            'filamento_material': p.filamento.material,
            'peso_filamento_g': str(p.peso_filamento_g),
            'comprimento_filamento_m': str(p.comprimento_filamento_m),
            'tempo_impressao_horas': str(p.tempo_impressao_horas),
            'preco_custo': str(p.preco_custo),
            'preco_venda': str(p.preco_venda),
            'estoque_quantidade': p.estoque_quantidade,
            'ativo': p.ativo,
        })
    return output.getvalue()


# ──────────────────────────────────────────────
# Importação por tipo
# ──────────────────────────────────────────────
def _import_fornecedores(rows):
    created = updated = skipped = 0
    for row in rows:
        nome = row.get('nome', '').strip()
        if not nome:
            skipped += 1
            continue
        _, is_new = Fornecedor.objects.update_or_create(
            nome=nome,
            defaults={
                'telefone': row.get('telefone', '').strip(),
                'email': row.get('email', '').strip(),
                'site': row.get('site', '').strip(),
                'observacoes': row.get('observacoes', '').strip(),
            },
        )
        if is_new:
            created += 1
        else:
            updated += 1
    return created, updated, skipped, []


def _safe_decimal(value, default='0'):
    try:
        return Decimal(str(value).strip() or default)
    except InvalidOperation:
        return Decimal(default)


def _import_filamentos(rows):
    created = updated = skipped = 0
    errors = []
    for row in rows:
        nome = row.get('nome', '').strip()
        cor = row.get('cor', '').strip()
        material = row.get('material', '').strip()
        if not nome or not cor or not material:
            skipped += 1
            continue

        fornecedor = None
        fornecedor_nome = row.get('fornecedor_nome', '').strip()
        if fornecedor_nome:
            fornecedor, _ = Fornecedor.objects.get_or_create(nome=fornecedor_nome)

        try:
            _, is_new = Filamento.objects.update_or_create(
                nome=nome, cor=cor, material=material,
                defaults={
                    'peso_total_g': _safe_decimal(row.get('peso_total_g'), '1000'),
                    'peso_disponivel_g': _safe_decimal(row.get('peso_disponivel_g'), '1000'),
                    'preco_por_kg': _safe_decimal(row.get('preco_por_kg'), '0.01'),
                    'fornecedor': fornecedor,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as exc:
            errors.append(f"Filamento '{nome}': {exc}")

    return created, updated, skipped, errors


def _import_produtos(rows):
    created = updated = skipped = 0
    errors = []
    for row in rows:
        nome = row.get('nome', '').strip()
        filamento_nome = row.get('filamento_nome', '').strip()
        filamento_cor = row.get('filamento_cor', '').strip()
        filamento_material = row.get('filamento_material', '').strip()

        if not nome:
            skipped += 1
            continue

        try:
            filamento = Filamento.objects.get(
                nome=filamento_nome,
                cor=filamento_cor,
                material=filamento_material,
            )
        except Filamento.DoesNotExist:
            errors.append(
                f"Produto '{nome}': filamento "
                f"'{filamento_nome} {filamento_cor} ({filamento_material})' não encontrado."
            )
            continue

        ativo_raw = row.get('ativo', 'True').strip().lower()
        ativo = ativo_raw in ('true', '1', 'yes', 'sim')

        try:
            _, is_new = Produto.objects.update_or_create(
                nome=nome, filamento=filamento,
                defaults={
                    'descricao': row.get('descricao', '').strip(),
                    'peso_filamento_g': _safe_decimal(row.get('peso_filamento_g'), '0.01'),
                    'comprimento_filamento_m': _safe_decimal(row.get('comprimento_filamento_m'), '0.01'),
                    'tempo_impressao_horas': _safe_decimal(row.get('tempo_impressao_horas'), '0.01'),
                    'preco_custo': _safe_decimal(row.get('preco_custo'), '0'),
                    'preco_venda': _safe_decimal(row.get('preco_venda'), '0.01'),
                    'estoque_quantidade': int(row.get('estoque_quantidade', '0') or '0'),
                    'ativo': ativo,
                },
            )
            if is_new:
                created += 1
            else:
                updated += 1
        except Exception as exc:
            errors.append(f"Produto '{nome}': {exc}")

    return created, updated, skipped, errors


# ──────────────────────────────────────────────
# Dispatcher central de importação
# ──────────────────────────────────────────────
_IMPORTERS = {
    'fornecedor': ('Fornecedores', _import_fornecedores),
    'filamento': ('Filamentos', _import_filamentos),
    'produto': ('Produtos', _import_produtos),
}


def _process_csv_content(content: str, filename: str = ''):
    """Detecta o tipo, importa as linhas e retorna (erros, mensagem_sucesso)."""
    reader = csv.DictReader(io.StringIO(content))
    rows = list(reader)
    if not rows:
        return [f"Arquivo '{filename}' está vazio ou sem dados."], []

    tipo = _detect_type(reader.fieldnames)
    if tipo is None:
        return [
            f"Arquivo '{filename}': cabeçalhos não reconhecidos. "
            f"Esperado: Fornecedores, Filamentos ou Produtos."
        ], []

    label, importer = _IMPORTERS[tipo]
    created, updated, skipped, errs = importer(rows)
    msgs = [
        f"{label} ({filename}): {created} criados, {updated} atualizados"
        + (f", {skipped} ignorados" if skipped else "") + "."
    ]
    return errs, msgs


# ──────────────────────────────────────────────
# Views
# ──────────────────────────────────────────────
@admin_group_required
def index(request):
    return render(request, 'importexport/index.html')


@admin_group_required
def exportar(request):
    if request.method != 'POST':
        return redirect('importexport:index')

    tipos = request.POST.getlist('tipos')
    if not tipos:
        messages.warning(request, 'Selecione ao menos um tipo para exportar.')
        return redirect('importexport:index')

    exports: dict[str, str] = {}
    if 'fornecedores' in tipos:
        exports['fornecedores.csv'] = _export_fornecedores()
    if 'filamentos' in tipos:
        exports['filamentos.csv'] = _export_filamentos()
    if 'produtos' in tipos:
        exports['produtos.csv'] = _export_produtos()

    if len(exports) == 1:
        fname, content = next(iter(exports.items()))
        response = HttpResponse(content, content_type='text/csv; charset=utf-8')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    # Múltiplos → ZIP
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for fname, content in exports.items():
            zf.writestr(fname, content.encode('utf-8'))
    buf.seek(0)
    response = HttpResponse(buf.read(), content_type='application/zip')
    response['Content-Disposition'] = 'attachment; filename="exportacao_grassato3d.zip"'
    return response


@admin_group_required
def importar(request):
    if request.method != 'POST':
        return redirect('importexport:index')

    arquivo = request.FILES.get('arquivo')
    if not arquivo:
        messages.error(request, 'Selecione um arquivo para importar.')
        return redirect('importexport:index')

    # Validação básica do nome do arquivo
    filename = arquivo.name
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    if ext not in ('csv', 'zip'):
        messages.error(request, 'Formato inválido. Envie um arquivo .csv ou .zip.')
        return redirect('importexport:index')

    all_errors: list[str] = []
    all_msgs: list[str] = []

    if ext == 'zip':
        try:
            with zipfile.ZipFile(arquivo, 'r') as zf:
                # Processar na ordem: fornecedores → filamentos → produtos
                csv_names = sorted(
                    [n for n in zf.namelist() if n.lower().endswith('.csv')],
                    key=lambda n: (
                        0 if 'fornecedor' in n.lower()
                        else (1 if 'filamento' in n.lower() else 2)
                    ),
                )
                for name in csv_names:
                    content = zf.read(name).decode('utf-8')
                    errs, msgs = _process_csv_content(content, name)
                    all_errors.extend(errs)
                    all_msgs.extend(msgs)
        except zipfile.BadZipFile:
            messages.error(request, 'Arquivo ZIP inválido ou corrompido.')
            return redirect('importexport:index')

    else:  # csv
        content = arquivo.read().decode('utf-8')
        errs, msgs = _process_csv_content(content, filename)
        all_errors.extend(errs)
        all_msgs.extend(msgs)

    for err in all_errors:
        messages.error(request, err)
    for msg in all_msgs:
        messages.success(request, msg)

    return redirect('importexport:index')
