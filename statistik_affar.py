# statistik_affar.py
import pandas as pd

def compute_business_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """Affärsrelaterad statistik från rader och inställningar."""
    stats = {}

    if rows.empty:
        return stats

    stats["Totalt antal scener"] = len(rows)
    stats["Totalt intäkt företag (USD)"] = rows.get("Intäkt företag", pd.Series(dtype=float)).sum()
    stats["Totalt intäkt känner (USD)"] = rows.get("Intäkt känner", pd.Series(dtype=float)).sum()
    stats["Totalt intäkt (USD)"] = rows.get("Intäkter", pd.Series(dtype=float)).sum()
    stats["Totalt kostnad män (USD)"] = rows.get("Kostnad män", pd.Series(dtype=float)).sum()
    stats["Totalt lön Malin (USD)"] = rows.get("Lön Malin", pd.Series(dtype=float)).sum()
    stats["Totalt vinst (USD)"] = rows.get("Vinst", pd.Series(dtype=float)).sum()
    stats["Totalt antal prenumeranter"] = rows.get("Prenumeranter", pd.Series(dtype=int)).sum()

    # BM-mål från konfiguration
    if "BM-mål" in cfg:
        stats["BM-mål (snitt)"] = round(cfg["BM-mål"], 2)
    if "Mål vikt" in cfg:
        stats["Mål vikt (kg)"] = round(cfg["Mål vikt"], 1)

    return stats
