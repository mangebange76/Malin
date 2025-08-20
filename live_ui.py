# live_ui.py
from datetime import datetime

def fmt_money(x):
    try:
        return f"${float(x):,.2f}"
    except Exception:
        return "$0.00"

def parse_iso_date(s):
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None
