# statistik_relation.py  (valfri – placeholder)
import pandas as pd

def compute(rows: pd.DataFrame, cfg: dict) -> dict:
    if rows is None or len(rows) == 0:
        return {}
    df = rows.copy()
    for c in ["Män","Svarta","Känner","Prenumeranter"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    out = {}
    if "Män" in df and "Svarta" in df:
        tot = float(df["Män"].sum() + df["Svarta"].sum())
        out["Svarta/(Män+Svarta) (%)"] = round(100.0 * float(df["Svarta"].sum())/tot, 2) if tot > 0 else 0.0
    out["Snitt prenumeranter per scen"] = round(float(df.get("Prenumeranter", 0).mean()), 2) if "Prenumeranter" in df else 0.0
    return out
