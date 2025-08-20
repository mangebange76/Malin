# statistik_affar.py  (valfri – placeholder)
import pandas as pd

def compute(rows: pd.DataFrame, cfg: dict) -> dict:
    if rows is None or len(rows) == 0:
        return {}
    df = rows.copy()
    for c in ["Intäkt företag","Vinst","Lön Malin","Intäkter","Kostnad män","Intäkt Känner"]:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return {
        "Snitt vinst per scen (USD)": round(df.get("Vinst", 0).mean(), 2) if "Vinst" in df else 0.0,
        "Max intäkt företag (USD)": round(df.get("Intäkt företag", 0).max(), 2) if "Intäkt företag" in df else 0.0,
    }
