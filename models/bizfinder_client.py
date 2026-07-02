# -*- coding: utf-8 -*-

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
                _("Bizfinder API %(method)s %(url)s failed: %(status)s %(detail)s")
                % {
                    'method': response.request.method,
                    'url': response.request.url,
                    'status': response.status_code,
                    'detail': detail,
                }
            )

    @api.model
    def _request(self, method: str, path: str, **kwargs) -> requests.Response:
        url, headers = self._creds()
        try:
            return requests.request(method, f"{url}{path}", headers=headers, **kwargs)
        except requests.RequestException as exc:
            raise UserError(
                _("Could not reach Bizfinder API %(url)s: %(error)s")
                % {'url': url, 'error': exc}
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
    def get_communities(self) -> list[dict]:
        r = self._request('GET', "/api/v1/insight/communities", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_sni(self) -> list[dict]:
        r = self._request('GET', "/api/v1/insight/sni", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def get_buckets(self) -> dict:
        r = self._request('GET', "/api/v1/insight/buckets", timeout=_TIMEOUT)
        self._check(r)
        return r.json()

    @api.model
    def sync_catalogues(self) -> dict:
        """Idempotent pull of the kommun / SNI / bucket / legal-form
        catalogues from the API into the local lookup models. Safe to
        call repeatedly — uses code/key as the natural key."""
        result = {'communities': 0, 'industries': 0, 'legal_forms': 0}

        Community = self.env['bizfinder.community'].sudo()
        Region = self.env['bizfinder.region'].sudo()
        existing_comm = {c.kommunkod: c for c in Community.search([])}
        region_by_code = {r.code: r.id for r in Region.search([])}
        # Dedupe by composite kommunkod defensively. The API endpoint
        # already DISTINCT ON (region, community), but an older
        # container could still ship duplicates and the unique(kommunkod)
        # constraint would crash the whole sync if so.
        by_kommunkod: dict[int, dict] = {}
        for entry in self.get_communities():
            kommunkod = int(entry['kommunkod'])
            by_kommunkod.setdefault(kommunkod, {
                'kommunkod': kommunkod,
                'community_code': int(entry.get('communityCode') or (kommunkod % 100)),
                'name': entry.get('name') or str(kommunkod),
                'region_id': region_by_code.get(entry.get('regionCode')) or False,
            })
        for kommunkod, vals in by_kommunkod.items():
            if kommunkod in existing_comm:
                existing_comm[kommunkod].write(vals)
            else:
                Community.create(vals)
            result['communities'] += 1

        # Industries are the primary user-facing picker; each entry maps
        # 1:1 to an SNI 2-digit group sourced from the API so the
        # catalogue stays in sync without manual XML curation.
        sni_payload = self.get_sni()
        Industry = self.env['bizfinder.industry'].sudo()
        existing_industry = {i.sni_prefixes: i for i in Industry.search([])}
        result.setdefault('industries', 0)
        for seq, entry in enumerate(sni_payload, start=1):
            code = str(entry['code'])
            name = entry.get('name') or code
            # Show as "62 Datakonsulter" so the user has the SNI prefix
            # alongside the friendly name.
            vals = {
                'name': f"{code} {name}",
                'sequence': seq * 10,
                'sni_prefixes': code,
            }
            industry = existing_industry.get(code)
            if industry:
                industry.write(vals)
            else:
                Industry.create(vals)
            result['industries'] += 1

        # Buckets endpoint is still called only for its legalForms list;
        # the employee/turnover bucket strings themselves live inside
        # bizfinder.magnitude.bucket_keys (seeded statically via XML).
        buckets = self.get_buckets()

        Legal = self.env['bizfinder.legal.form'].sudo()
        existing_legal = {l.code: l for l in Legal.search([])}
        for seq, entry in enumerate(buckets.get('legalForms') or [], start=1):
            code = str(entry['code'])
            vals = {'code': code, 'name': entry.get('name') or code, 'sequence': seq * 10}
            if code in existing_legal:
                existing_legal[code].write(vals)
            else:
                Legal.create(vals)
            result['legal_forms'] += 1

        # Seed the built-in segments as managed presets (create-if-missing).
        result['presets'] = self.env['bizfinder.preset']._seed_builtin_presets()

        return result

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
