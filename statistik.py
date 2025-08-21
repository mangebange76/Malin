# statistik.py
import pandas as pd

def _num(series, as_int=False):
    s = pd.to_numeric(series, errors="coerce").fillna(0)
    return s.astype(int) if as_int else s.astype(float)

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """
    Minimal, robust statistik tills vi bygger ut.
    - Summerar intäkter/kostnader/vinst
    - Totalt antal prenumeranter
    - BM-mål & mål-vikt från ackumulerade värden i cfg (BM_ACC_SUM, BM_ACC_N) + HEIGHT_M
    """
    stats = {}
    if rows is None or rows.empty:
        # visa i alla fall BM-mål om det finns i cfg
        bm_sum = float(cfg.get("BM_ACC_SUM", 0))
        bm_n   = int(cfg.get("BM_ACC_N", 0))
        bm_avg = round(bm_sum / bm_n, 2) if bm_n > 0 else 0.0
        height_m = float(cfg.get("HEIGHT_M", 1.64))
        target_w = round(bm_avg * (height_m ** 2), 1) if bm_avg > 0 else 0.0
        return {
            "Totalt antal scener": 0,
            "Totalt antal prenumeranter": 0,
            "BM-mål (snitt)": bm_avg,
            "Mål vikt (kg)": target_w,
        }

    stats["Totalt antal scener"] = len(rows)

    # Summor (robust)
    for col, label in [
        ("Intäkter", "Totalt intäkter (USD)"),
        ("Kostnad män", "Totalt kostnad män (USD)"),
        ("Intäkt Känner", "Totalt intäkt känner (USD)"),
        ("Intäkt företag", "Totalt intäkt företag (USD)"),
        ("Lön Malin", "Totalt lön Malin (USD)"),
        ("Vinst", "Totalt vinst (USD)"),
    ]:
        if col in rows.columns:
            stats[label] = float(_num(rows[col]).sum())
        else:
            stats[label] = 0.0

    # Prenumeranter
    if "Prenumeranter" in rows.columns:
        stats["Totalt antal prenumeranter"] = int(_num(rows["Prenumeranter"]).sum())
    else:
        stats["Totalt antal prenumeranter"] = 0

    # BM-mål från CFG-ackumulatorer
    bm_sum = float(cfg.get("BM_ACC_SUM", 0))
    bm_n   = int(cfg.get("BM_ACC_N", 0))
    bm_avg = round(bm_sum / bm_n, 2) if bm_n > 0 else 0.0
    height_m = float(cfg.get("HEIGHT_M", 1.64))
    target_w = round(bm_avg * (height_m ** 2), 1) if bm_avg > 0 else 0.0

    stats["BM-mål (snitt)"] = bm_avg
    stats["Mål vikt (kg)"]  = target_w

    return stats
