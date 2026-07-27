
import logging

import requests
from odoo import _, api, fields, models
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
        url, access_token = self.env['res.config.settings'].get_bizfinder_credentials()
        if not url:
            raise UserError(_("Bizfinder API URL is not configured."))
        if not access_token:
            raise UserError(_("Bizfinder access token is not configured."))
        headers = {
            'Authorization': f'Bearer {access_token}',
            'X-Odoo-Db': self.env.cr.dbname,
            'X-Odoo-Company-Id': str(self.env.company.id),
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
                _(
                    "Bizfinder API %(method)s %(url)s failed: %(status)s %(detail)s",
                    method=response.request.method,
                    url=response.request.url,
                    status=response.status_code,
                    detail=detail,
                )
            )

    @api.model
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url, headers = self._creds()
        try:
            # Every caller passes timeout=_TIMEOUT via **kwargs.
            return requests.request(  # noqa: S113  pylint: disable=external-request-timeout
                method, f"{url}{path}", headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise UserError(
                _("Could not reach Bizfinder API %(url)s: %(error)s", url=url, error=exc)
            ) from exc

    @api.model
    def validate(self) -> bool:
        r = self._request('GET', "/api/v1/insight/validatelogin", timeout=_TIMEOUT)
        self._check(r)
        return True

    @api.model
    def get_filters(self) -> list[dict]:
        r = self._request('GET', "/api/v1/insight/filters", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_segments(self) -> list[dict]:
        r = self._request('GET', "/api/v1/insight/segments", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_billing_pricing(self) -> dict:
        r = self._request('GET', "/api/v1/billing/pricing", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_billing_usage(self, date_from, date_to) -> dict:
        r = self._request(
            'GET',
            "/api/v1/billing/usage",
            params={'from': fields.Date.to_string(date_from), 'to': fields.Date.to_string(date_to)},
            timeout=_TIMEOUT,
        )
        self._check(r)
        return r.json()

    @api.model
    def preview(self, values: list[dict]) -> int:
        r = self._request('POST', "/api/v1/insight/filters", json=values, timeout=_TIMEOUT)
        self._check(r)
        return int(r.json().get('hitCount', 0))

    @api.model
    def search(self, values: list[dict], skip: int = 0, take: int = 200) -> list[dict]:
        r = self._request(
            'POST',
            "/api/v1/insight/prospects",
            params={'skip': skip, 'take': take},
            json=values,
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()

    @api.model
    def company_status(self, org_numbers: list[str]) -> list[dict]:
        """Fetch current registry status + key financials for the given org
        numbers (max 5000 per call). Free (not billed), no contact fields."""
        if not org_numbers:
            return []
        r = self._request(
            'POST',
            "/api/v1/insight/company-status",
            json={'orgNumbers': list(org_numbers)},
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()

    @api.model
    def events(self, org_numbers: list[str], since: str | None = None) -> list[dict]:
        """Fetch change events for the given org numbers (max 5000 per call),
        ordered by detectedAt asc. ``since`` is an ISO datetime string or None
        for no lower bound. Free (not billed)."""
        if not org_numbers:
            return []
        r = self._request(
            'POST',
            "/api/v1/insight/events",
            json={'orgNumbers': list(org_numbers), 'since': since},
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()

    @api.model
    def lookup(self, query: str, take: int = 10) -> list[dict]:
        """Autocomplete-style company lookup (digits match orgnr prefix, text
        matches name). Free (not billed), redacted tier: no street/phone."""
        r = self._request(
            'GET',
            "/api/v1/insight/lookup",
            params={'q': query, 'take': take},
            timeout=_TIMEOUT,
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
            "/api/v1/insight/reveal",
            json={'orgNumbers': list(org_numbers)},
            timeout=_TIMEOUT * 2,
        )
        self._check(r)
        return r.json()
