# statistik.py
import pandas as pd

def compute_stats(rows, cfg):
    """Minimal placeholder tills vi bygger riktiga statistiken."""
    stats = {
        "Totalt antal rader": len(rows),
        "Totala intäkter": rows.get("Intäkt företag", pd.Series(dtype=float)).sum(),
        "Totala lön Malin": rows.get("Lön Malin", pd.Series(dtype=float)).sum(),
    }
    return stats
