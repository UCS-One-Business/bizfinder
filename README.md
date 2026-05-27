# bizfinder

Custom Odoo 19 addon that searches the Creditsafe-backed `bizfinder_api`
service and turns prospects into `crm.lead` records.

## Setup

1. Configure the FastAPI service in **Settings → Bizfinder**:
   - API URL (default `http://bizfinder_api:8000` for compose stack)
   - API Key issued by the Bizfinder service
2. Open **CRM → New Prospect Search**.
3. Fill in filters (comma-separated codes, see field tooltips), hit
   **Preview count** to see hits, then **Search** to load results.
4. Tick rows and **Create leads from selected**.

The results toolbar shows the selected reveal count and estimated cost before
lead creation. Sales managers can review actual billed usage from
**CRM → Bizfinder Usage**; totals come from the API reveal log.

## Filter codes

| Field | Examples |
|---|---|
| Regions | `1` (Stockholm), `12` (Skåne), `14` (Västra Götaland) |
| SNI prefixes | `62` (datakonsulter), `70` (konsult), `41` (husbyggnad) |
| Legal forms | `AB`, `EF`, `HB/KB`, `OVR` |
| Turnover buckets | `5000 - 9999 tkr`, `10000 - 19999 tkr` |
| Employee buckets | `5-9 anställda`, `10-19 anställda` |

VAT is written as `SE<orgnr>01` for parity with prior modules' quality
filter; the raw org number is also kept on `crm.lead.ref`.
