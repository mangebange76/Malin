# statistik.py
import pandas as pd

def compute_stats(rows: pd.DataFrame, cfg=None) -> dict:
    stats = {}
    if rows is None or rows.empty:
        return stats

    # Simple summeringar – säkra mot str-kolumner
    def _num(s, default=0.0):
        try:
            return float(s)
        except Exception:
            return default

    stats["Totalt antal scener"] = len(rows)

    for col, label in [
        ("Intäkt företag", "Totalt intäkt företag (USD)"),
        ("Intäkt Känner", "Totalt intäkt känner (USD)"),
        ("Intäkter", "Totalt intäkter (USD)"),
        ("Kostnad män", "Totalt kostnad män (USD)"),
        ("Lön Malin", "Totalt lön Malin (USD)"),
        ("Vinst", "Totalt vinst (USD)"),
    ]:
        if col in rows.columns:
            stats[label] = sum(_num(v) for v in rows[col].tolist())

    if "Prenumeranter" in rows.columns:
        stats["Totalt antal prenumeranter"] = int(sum(_num(v) for v in rows["Prenumeranter"].tolist()))

    return stats
