# statistik_relation.py
import pandas as pd

def compute_relation_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """Relationsstatistik (fitta, älskar, sover etc.)"""
    stats = {}

    if rows.empty:
        return stats

    stats["Totalt antal män"] = rows.get("Totalt Män", pd.Series(dtype=int)).sum()
    stats["Total fitta"] = rows.get("Fitta", pd.Series(dtype=int)).sum()
    stats["Totalt älskar"] = rows.get("Älskar", pd.Series(dtype=int)).sum()
    stats["Totalt sover med"] = rows.get("Sover med", pd.Series(dtype=int)).sum()

    antal_scener = len(rows)
    stats["Andel älskar (%)"] = round(100 * stats["Totalt älskar"] / antal_scener, 1) if antal_scener > 0 else "-"
    stats["Andel sover med (%)"] = round(100 * stats["Totalt sover med"] / antal_scener, 1) if antal_scener > 0 else "-"

    try:
        svarta = rows.get("Svarta", pd.Series(dtype=int)).sum()
        män_totalt = (
            rows.get("Män", pd.Series(dtype=int)).sum()
            + cfg.get("Känner Sammanlagt", 0)
            + rows.get("Svarta", pd.Series(dtype=int)).sum()
            + cfg.get("Bekanta", 0)
            + rows.get("Eskilstuna killar", pd.Series(dtype=int)).sum()
            + rows.get("Bonus deltagit", pd.Series(dtype=int)).sum()
            + cfg.get("Personal", 0)
        )
        stats["Andel svarta (%)"] = round(100 * svarta / män_totalt, 2) if män_totalt > 0 else 0
    except:
        stats["Andel svarta (%)"] = "?"

    return stats
