# statistik.py
import pandas as pd

def compute_stats(rows, cfg):
    """Minimal placeholder tills vi bygger riktiga statistiken."""
    df = pd.DataFrame(rows or [])

    stats = {
        "Totalt antal rader": int(len(df)),
        "Totala intäkter": float(df.get("Intäkt företag", pd.Series(dtype=float)).fillna(0).sum()),
        "Totala lön Malin": float(df.get("Lön Malin", pd.Series(dtype=float)).fillna(0).sum()),
    }
    return stats
