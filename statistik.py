# statistik.py
import pandas as pd

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """Beräknar grundläggande statistik från alla rader + inställningar."""
    stats = {}

    if rows.empty:
        return stats

    # Totalt antal rader
    stats["Totalt antal scener"] = len(rows)

    # Summeringar
    stats["Totalt intäkt företag (USD)"] = rows.get("Intäkt företag", pd.Series(dtype=float)).sum()
    stats["Totalt intäkt känner (USD)"] = rows.get("Intäkt känner", pd.Series(dtype=float)).sum()
    stats["Totalt intäkt (USD)"] = rows.get("Intäkter", pd.Series(dtype=float)).sum()
    stats["Totalt kostnad män (USD)"] = rows.get("Kostnad män", pd.Series(dtype=float)).sum()
    stats["Totalt lön Malin (USD)"] = rows.get("Lön Malin", pd.Series(dtype=float)).sum()
    stats["Totalt vinst (USD)"] = rows.get("Vinst", pd.Series(dtype=float)).sum()

    # Totalt antal prenumeranter
    stats["Totalt antal prenumeranter"] = rows.get("Prenumeranter", pd.Series(dtype=int)).sum()

    # BM-mål
    if "BM-mål" in cfg:
        stats["BM-mål (snitt)"] = round(cfg["BM-mål"], 2)
    if "Mål vikt" in cfg:
        stats["Mål vikt (kg)"] = round(cfg["Mål vikt"], 1)

    # Andel svarta
    try:
        svarta = rows["Svarta"].sum()
        män_totalt = (
            rows["Män"].sum()
            + cfg.get("Känner Sammanlagt", 0)
            + rows["Svarta"].sum()
            + cfg.get("Bekanta", 0)
            + rows["Eskilstuna killar"].sum()
            + rows["Bonus deltagit"].sum()
            + cfg.get("Personal", 0)
        )
        stats["Andel svarta (%)"] = round(100 * svarta / män_totalt, 2) if män_totalt > 0 else 0
    except:
        stats["Andel svarta (%)"] = "?"

    return stats
