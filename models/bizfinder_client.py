# -*- coding: utf-8 -*-

import logging

import requests

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

_TIMEOUT = 30


class BizfinderClient(models.AbstractModel):
    """Thin HTTP client for the bizfinder_api FastAPI service.

    All methods raise UserError on non-2xx so the wizard can surface a
    meaningful message; per AGENTS.md no silent fallbacks.
    """
    _name = 'bizfinder.client'
    _description = 'Bizfinder API Client'

    @api.model
    def _creds(self) -> tuple[str, dict]:
        url, api_key = self.env['res.config.settings'].get_bizfinder_credentials()
        if not url:
            raise UserError("Bizfinder API URL is not configured.")
        if not api_key:
            raise UserError("Bizfinder API key is not configured.")
        headers = {
            'Authorization': f'Bearer {api_key}',
            'X-Odoo-Db': self.env.cr.dbname,
            'X-Odoo-User-Id': str(self.env.user.id),
            'X-Odoo-User-Login': self.env.user.login or '',
        }
        return url.rstrip('/'), headers

    @api.model
    def _check(self, response: requests.Response) -> None:
        if not response.ok:
            try:
                detail = response.json()
            except Exception:
                detail = response.text
            raise UserError(
                f"Bizfinder API {response.request.method} {response.request.url} "
                f"failed: {response.status_code} {detail}"
            )

    @api.model
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url, headers = self._creds()
        try:
            return requests.request(method, f"{url}{path}", headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise UserError(f"Could not reach Bizfinder API {url}: {exc}") from exc

    @api.model
    def validate(self) -> bool:
        r = self._request('GET', "/api/insight/validatelogin", timeout=_TIMEOUT)
        return r.ok

    @api.model
    def get_filters(self) -> list[dict]:
        r = self._request('GET', "/api/insight/filters", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_segments(self) -> list[dict]:
        r = self._request('GET', "/api/insight/segments", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_billing_pricing(self) -> dict:
        r = self._request('GET', "/api/billing/pricing", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_billing_usage(self, date_from, date_to) -> dict:
        r = self._request(
            'GET',
            "/api/billing/usage",
            params={'from': fields.Date.to_string(date_from), 'to': fields.Date.to_string(date_to)},
            timeout=_TIMEOUT,
        )
        self._check(r)
        return r.json()

    @api.model
    def preview(self, values: list[dict]) -> int:
        r = self._request('POST', "/api/insight/filters", json=values, timeout=_TIMEOUT)
        self._check(r)
        return int(r.json().get('hitCount', 0))

    @api.model
    def search(self, values: list[dict], skip: int = 0, take: int = 200) -> list[dict]:
        r = self._request(
            'POST',
            "/api/insight/prospects",
            params={'skip': skip, 'take': take},
            json=values,
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()

    @api.model
    def reveal(self, org_numbers: list[str]) -> list[dict]:
        """Fetch un-redacted contact info for the given org numbers.
        Each call is billed server-side (one row in reveal_log per org)."""
        if not org_numbers:
            return []
        r = self._request(
            'POST',
            "/api/insight/reveal",
            json={'orgNumbers': list(org_numbers)},
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()
