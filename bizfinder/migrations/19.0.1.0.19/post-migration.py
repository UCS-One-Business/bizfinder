"""Backfill the new range defaults into existing ``bizfinder.search``
rows.

Field-level ``default=`` only fires when a record is created. Wizards
that were created before defaults were added (or that the user has
bookmarked at ``/odoo/prospect/<id>``) show empty inputs and fall back
to placeholder text. Writing the defaults onto every still-existing
transient row makes the pre-fill visible without forcing the user to
reopen the wizard from the menu.
"""

# (column, default_value). Mirrors the field-level defaults in
# bizfinder_search.py. Strings include thin / regular spaces — the
# _range_value parser already strips them.
_RANGE_DEFAULTS = [
    ("net_sales_min", "-10 000 000"),
    ("net_sales_max", "100 000 000"),
    ("net_operating_income_min", "-10 000 000"),
    ("net_operating_income_max", "100 000 000"),
    ("operating_result_min", "-10 000 000"),
    ("operating_result_max", "100 000 000"),
    ("profit_after_fin_min", "-10 000 000"),
    ("profit_after_fin_max", "100 000 000"),
    ("net_profit_loss_min", "-10 000 000"),
    ("net_profit_loss_max", "100 000 000"),
    ("growth_pct_min", "-100"),
    ("growth_pct_max", "500"),
    ("headcount_change_min", "-100"),
    ("headcount_change_max", "500"),
    ("solidity_pct_min", "-100"),
    ("solidity_pct_max", "100"),
    ("operating_margin_min", "-100"),
    ("operating_margin_max", "100"),
    ("profit_margin_min", "-100"),
    ("profit_margin_max", "100"),
    ("quick_ratio_min", "0"),
    ("quick_ratio_max", "1000"),
    ("turnover_per_employee_min", "0"),
    ("turnover_per_employee_max", "100 000"),
    ("employees_min", "0"),
    ("employees_max", "100 000"),
    ("cash_min", "0"),
    ("cash_max", "10 000 000"),
    ("assets_min", "0"),
    ("assets_max", "100 000 000"),
    ("equity_min", "-10 000 000"),
    ("equity_max", "100 000 000"),
    ("current_liabilities_min", "0"),
    ("current_liabilities_max", "100 000 000"),
    ("long_term_debts_min", "0"),
    ("long_term_debts_max", "100 000 000"),
    ("account_months_min", "0"),
    ("account_months_max", "24"),
    ("dividend_min", "0"),
    ("dividend_max", "100 000 000"),
]


_DATE_FROM_FLOOR = "1900-01-01"

# Columns that should default to the floor date (~"any time before").
_DATE_FROM_COLS = (
    "registration_date_from",
    "status_date_from",
    "reservation_date_from",
)

# Columns that should default to today (~"any time up to now").
_DATE_TO_COLS = (
    "registration_date_to",
    "status_date_to",
    "reservation_date_to",
)


def migrate(cr, version):
    for col, value in _RANGE_DEFAULTS:
        # Idempotent: re-running just no-ops on already-filled rows.
        cr.execute(
            f"UPDATE bizfinder_search SET {col} = %s "
            f"WHERE {col} IS NULL OR {col} = ''",
            (value,),
        )
    # The previous upgrade set *_from to "today minus 20 years" which
    # mistakenly excluded older companies. Overwrite anything <= the
    # old default cutoff so users on existing wizards immediately see
    # the corrected floor. Hand-edited values older than that are kept.
    for col in _DATE_FROM_COLS:
        cr.execute(
            f"UPDATE bizfinder_search SET {col} = %s "
            f"WHERE {col} IS NULL OR {col} >= (CURRENT_DATE - INTERVAL '25 years')",
            (_DATE_FROM_FLOOR,),
        )
    for col in _DATE_TO_COLS:
        cr.execute(
            f"UPDATE bizfinder_search SET {col} = CURRENT_DATE WHERE {col} IS NULL",
        )
