"""Reset stale ``today - 20 years`` floor dates on existing wizards.

The 19.0.1.0.19 migration filled the ``*_from`` columns with a rolling
"today minus 20 years" date, which read as misleading 2006 to users
expecting a true earliest-companies floor. We now use 1900-01-01.
Apply that correction onto any row still showing the old-style default
so the user doesn't have to reopen the wizard from the menu.
"""

_FLOOR = "1900-01-01"
_FROM_COLS = (
    "registration_date_from",
    "status_date_from",
    "reservation_date_from",
)


def migrate(cr, version):
    for col in _FROM_COLS:
        cr.execute(
            f"UPDATE bizfinder_search SET {col} = %s "
            f"WHERE {col} IS NULL "
            f"   OR {col} >= (CURRENT_DATE - INTERVAL '25 years')",
            (_FLOOR,),
        )
