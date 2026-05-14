"""
Serviço de integração com a API do MercadoLivre (Brasil).

Documentação oficial: https://developers.mercadolivre.com.br/
"""
import logging
from datetime import timedelta

import requests
from django.utils import timezone

logger = logging.getLogger(__name__)

AUTH_BASE = 'https://auth.mercadolivre.com.br'
API_BASE = 'https://api.mercadolibre.com'

# Listing type para "Clássico" no ML Brasil
LISTING_TYPE_CLASSICO = 'gold_special'


class MercadoLivreService:
    """Encapsula todas as chamadas à API do MercadoLivre."""

    # ── OAuth ─────────────────────────────────────────────────────────────────

    def get_authorization_url(self, client_id: str, redirect_uri: str, state: str = '') -> str:
        params = f'response_type=code&client_id={client_id}&redirect_uri={redirect_uri}'
        if state:
            params += f'&state={state}'
        return f'{AUTH_BASE}/authorization?{params}'

    def exchange_code(self, integracao, code: str, redirect_uri: str) -> tuple[bool, str]:
        """Troca o authorization code pelo access_token/refresh_token.
        Retorna (True, '') em caso de sucesso ou (False, mensagem_de_erro).
        """
        try:
            resp = requests.post(
                f'{API_BASE}/oauth/token',
                data={
                    'grant_type': 'authorization_code',
                    'client_id': integracao.client_id,
                    'client_secret': integracao.client_secret,
                    'code': code,
                    'redirect_uri': redirect_uri,
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error('ML exchange_code request error: %s', exc)
            return False, str(exc)

        if resp.ok:
            self._save_token(integracao, resp.json())
            return True, ''

        try:
            detail = resp.json()
            error_msg = detail.get('message') or detail.get('error_description') or detail.get('error') or resp.text
        except Exception:
            error_msg = resp.text

        logger.error('ML exchange_code error %s: %s', resp.status_code, error_msg)
        return False, f'[{resp.status_code}] {error_msg}'

    def refresh_token(self, integracao) -> bool:
        """Renova o access_token usando o refresh_token armazenado."""
        if not integracao.refresh_token:
            logger.warning('ML refresh_token: sem refresh_token armazenado para %s — marcando reauth.', integracao)
            integracao.needs_reauth = True
            integracao.save(update_fields=['needs_reauth', 'atualizado_em'])
            return False
        try:
            resp = requests.post(
                f'{API_BASE}/oauth/token',
                data={
                    'grant_type': 'refresh_token',
                    'client_id': integracao.client_id,
                    'client_secret': integracao.client_secret,
                    'refresh_token': integracao.refresh_token,
                },
                timeout=15,
            )
        except requests.RequestException as exc:
            logger.error('ML refresh_token request error: %s', exc)
            return False

        if resp.ok:
            self._save_token(integracao, resp.json())
            return True
        logger.error('ML refresh_token error %s: %s', resp.status_code, resp.text)
        # Marca que é necessária reautorização manual
        integracao.needs_reauth = True
        integracao.save(update_fields=['needs_reauth', 'atualizado_em'])
        return False

    def _save_token(self, integracao, data: dict) -> None:
        expires_in = data.get('expires_in', 21600)  # ML default: 6h
        integracao.access_token = data['access_token']
        integracao.refresh_token = data.get('refresh_token', integracao.refresh_token)
        integracao.token_expires_at = timezone.now() + timedelta(seconds=expires_in)
        integracao.ml_user_id = str(data.get('user_id', integracao.ml_user_id or ''))
        integracao.needs_reauth = False  # token renovado com sucesso
        integracao.save(update_fields=[
            'access_token', 'refresh_token', 'token_expires_at', 'ml_user_id',
            'needs_reauth', 'atualizado_em',
        ])

    def _headers(self, integracao) -> dict:
        """Retorna headers de autenticação, renovando token se necessário."""
        if integracao.token_expires_at and timezone.now() >= integracao.token_expires_at:
            self.refresh_token(integracao)
        return {
            'Authorization': f'Bearer {integracao.access_token}',
            'Content-Type': 'application/json',
        }

    def _request(self, method: str, url: str, integracao, **kwargs) -> requests.Response:
        """
        Executa uma requisição autenticada com retry automático em caso de 401.
        Se o token estiver expirado/inválido, tenta renovar uma vez e repete.
        """
        resp = requests.request(method, url, headers=self._headers(integracao), **kwargs)
        if resp.status_code == 401:
            logger.info('ML 401 recebido para %s — tentando renovar token.', url)
            if self.refresh_token(integracao):
                resp = requests.request(method, url, headers=self._headers(integracao), **kwargs)
            else:
                logger.error('ML refresh_token falhou para %s — reautorização manual necessária.', integracao)
                # Safety net: garante que needs_reauth está marcado independente do caminho de falha
                if not integracao.needs_reauth:
                    integracao.needs_reauth = True
                    integracao.save(update_fields=['needs_reauth', 'atualizado_em'])
        return resp

    # ── Itens / Anúncios ──────────────────────────────────────────────────────

    def create_listing(self, integracao, produto_integracao) -> tuple[dict | None, str]:
        """
        Publica o produto como anúncio Clássico no ML.
        Retorna (item_dict, '') em sucesso ou (None, mensagem_de_erro) em falha.
        """
        import json as _json
        produto = produto_integracao.produto

        # ── Fotos ────────────────────────────────────────────────────────────
        pictures = []
        if produto_integracao.picture_urls:
            for url in produto_integracao.picture_urls.strip().splitlines():
                url = url.strip()
                if url:
                    pictures.append({'source': url})

        # ── Atributos obrigatórios da categoria ───────────────────────────────
        attributes = []
        if produto_integracao.ml_attributes_json:
            try:
                attrs = _json.loads(produto_integracao.ml_attributes_json)
                for attr_id, value in attrs.items():
                    if value:
                        attributes.append({'id': attr_id, 'value_name': str(value)})
            except (ValueError, AttributeError) as exc:
                logger.warning('ml_attributes_json parse error: %s', exc)

        payload = {
            'title': produto.nome,
            'category_id': produto_integracao.categoria_ml,
            'price': float(produto.preco_venda),
            'currency_id': 'BRL',
            'available_quantity': max(produto.estoque_quantidade, 1),
            'buying_mode': 'buy_it_now',
            'listing_type_id': LISTING_TYPE_CLASSICO,
            'condition': 'new',
            'description': {'plain_text': produto.descricao or produto.nome},
            'shipping': {
                'mode': 'me2',
                'free_shipping': True,
            },
        }
        if pictures:
            payload['pictures'] = pictures
        if attributes:
            payload['attributes'] = attributes

        try:
            resp = self._request('POST', f'{API_BASE}/items', integracao, json=payload, timeout=20)
        except requests.RequestException as exc:
            logger.error('ML create_listing request error: %s', exc)
            return None, str(exc)

        if resp.ok:
            data = resp.json()
            logger.info('ML listing created: %s', data.get('id'))
            return data, ''

        # Extrai mensagem de erro da API
        try:
            err_data = resp.json()
            causes = err_data.get('cause', [])
            errors = [c['message'] for c in causes if c.get('type') == 'error']
            error_msg = ' | '.join(errors) if errors else (err_data.get('message') or resp.text)
        except Exception:
            error_msg = resp.text

        logger.error('ML create_listing error %s: %s', resp.status_code, error_msg)
        return None, f'[{resp.status_code}] {error_msg}'

    def get_category_attributes(self, category_id: str, integracao=None) -> list:
        """
        Retorna os atributos da categoria.
        Use integracao para chamadas autenticadas (melhor rate limit).
        """
        try:
            if integracao:
                resp = self._request('GET', f'{API_BASE}/categories/{category_id}/attributes',
                                     integracao, timeout=10)
            else:
                resp = requests.get(
                    f'{API_BASE}/categories/{category_id}/attributes',
                    headers={'User-Agent': 'grassato-3d/1.0'},
                    timeout=10,
                )
        except requests.RequestException as exc:
            logger.error('ML get_category_attributes error: %s', exc)
            return []
        return resp.json() if resp.ok else []

    def update_stock(self, integracao, item_id: str, quantity: int) -> bool:
        """Atualiza a quantidade disponível do anúncio."""
        return self.update_listing(integracao, item_id, {'available_quantity': max(quantity, 0)})

    def update_listing(self, integracao, item_id: str, payload: dict) -> bool:
        """Atualiza campos arbitrários de um anúncio (título, preço, estoque, etc.)."""
        try:
            resp = self._request('PUT', f'{API_BASE}/items/{item_id}', integracao,
                                 json=payload, timeout=10)
        except requests.RequestException as exc:
            logger.error('ML update_listing request error: %s', exc)
            return False

        if resp.ok:
            return True
        logger.error('ML update_listing error %s for %s: %s', resp.status_code, item_id, resp.text)
        return False

    def pause_listing(self, integracao, item_id: str) -> bool:
        """Pausa o anúncio no ML (produto sem estoque ou excluído)."""
        try:
            resp = self._request('PUT', f'{API_BASE}/items/{item_id}', integracao,
                                 json={'status': 'paused'}, timeout=10)
        except requests.RequestException as exc:
            logger.error('ML pause_listing request error: %s', exc)
            return False
        return resp.ok

    def activate_listing(self, integracao, item_id: str) -> bool:
        """Reativa um anúncio pausado."""
        try:
            resp = self._request('PUT', f'{API_BASE}/items/{item_id}', integracao,
                                 json={'status': 'active'}, timeout=10)
        except requests.RequestException as exc:
            logger.error('ML activate_listing request error: %s', exc)
            return False
        return resp.ok

    def get_item(self, integracao, item_id: str) -> dict | None:
        """Busca detalhes do item no ML."""
        try:
            resp = self._request('GET', f'{API_BASE}/items/{item_id}', integracao, timeout=10)
        except requests.RequestException as exc:
            logger.error('ML get_item request error: %s', exc)
            return None
        return resp.json() if resp.ok else None

    def get_order(self, integracao, order_id: str) -> dict | None:
        """Busca detalhes de um pedido no ML."""
        try:
            resp = self._request('GET', f'{API_BASE}/orders/{order_id}', integracao, timeout=10)
        except requests.RequestException as exc:
            logger.error('ML get_order request error: %s', exc)
            return None
        return resp.json() if resp.ok else None

    # ── Categorias ────────────────────────────────────────────────────────────

    @staticmethod
    def search_categories(term: str, site: str = 'MLB') -> list:
        """
        Busca categorias usando o domain_discovery do ML (sem autenticação).
        Retorna lista de {'category_id', 'category_name', 'domain_name'}.
        """
        try:
            resp = requests.get(
                f'{API_BASE}/sites/{site}/domain_discovery/search',
                params={'q': term, 'limit': 8},  # API aceita no máximo 8
                headers={'User-Agent': 'grassato-3d/1.0'},
                timeout=10,
            )
        except requests.RequestException as exc:
            logger.error('ML search_categories error: %s', exc)
            return []
        if resp.ok:
            return resp.json() if isinstance(resp.json(), list) else []
        logger.error('ML search_categories error %s: %s', resp.status_code, resp.text)
        return []

    def get_root_categories(self, integracao=None, site: str = 'MLB') -> list:
        """Retorna as categorias raiz do ML (requer token)."""
        try:
            if integracao:
                resp = self._request('GET', f'{API_BASE}/sites/{site}/categories',
                                     integracao, timeout=10)
            else:
                resp = requests.get(
                    f'{API_BASE}/sites/{site}/categories',
                    headers={'User-Agent': 'grassato-3d/1.0'},
                    timeout=10,
                )
        except requests.RequestException as exc:
            logger.error('ML get_root_categories error: %s', exc)
            return []
        return resp.json() if resp.ok else []

    def get_category_children(self, category_id: str, integracao=None) -> dict:
        """Retorna dados e filhos de uma categoria (requer token para subcategorias)."""
        try:
            if integracao:
                resp = self._request('GET', f'{API_BASE}/categories/{category_id}',
                                     integracao, timeout=10)
            else:
                resp = requests.get(
                    f'{API_BASE}/categories/{category_id}',
                    headers={'User-Agent': 'grassato-3d/1.0'},
                    timeout=10,
                )
        except requests.RequestException as exc:
            logger.error('ML get_category_children error: %s', exc)
            return {}
        return resp.json() if resp.ok else {}

