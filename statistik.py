# statistik.py
import pandas as pd

def _num(s):
    try:
        return float(s)
    except Exception:
        return 0.0

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    stats = {}
    if rows is None or len(rows) == 0:
        return stats
    if not isinstance(rows, pd.DataFrame):
        rows = pd.DataFrame(rows)

    # säker konvertering av relevanta kolumner
    for col in [
        "Intäkter","Kostnad män","Intäkt Känner","Intäkt företag","Lön Malin","Vinst",
        "Prenumeranter","Svarta","Män","Eskilstuna killar","Bonus deltagit"
    ]:
        if col in rows.columns:
            rows[col] = pd.to_numeric(rows[col], errors="coerce").fillna(0)

    stats["Totalt antal scener"] = len(rows)
    stats["Totalt antal prenumeranter"] = int(rows.get("Prenumeranter", pd.Series(dtype=float)).sum())
    stats["Totalt intäkter (USD)"]      = round(rows.get("Intäkter", pd.Series(dtype=float)).sum(), 2)
    stats["Totalt kostnad män (USD)"]   = round(rows.get("Kostnad män", pd.Series(dtype=float)).sum(), 2)
    stats["Totalt intäkt känner (USD)"] = round(rows.get("Intäkt Känner", pd.Series(dtype=float)).sum(), 2)
    stats["Totalt intäkt företag (USD)"]= round(rows.get("Intäkt företag", pd.Series(dtype=float)).sum(), 2)
    stats["Totalt lön Malin (USD)"]     = round(rows.get("Lön Malin", pd.Series(dtype=float)).sum(), 2)
    stats["Totalt vinst (USD)"]         = round(rows.get("Vinst", pd.Series(dtype=float)).sum(), 2)

    # Andel svarta (%) enligt din definition på statistiknivå
    svarta_sum = rows.get("Svarta", pd.Series(dtype=float)).sum()
    men_sum    = rows.get("Män", pd.Series(dtype=float)).sum()
    esk_sum    = rows.get("Eskilstuna killar", pd.Series(dtype=float)).sum()
    bonus_sum  = rows.get("Bonus deltagit", pd.Series(dtype=float)).sum()
    # Känner sammanlagt från cfg maxvärden
    kanner_sammanlagt = (
        _num(cfg.get("MAX_PAPPAN",0)) + _num(cfg.get("MAX_GRANNAR",0)) +
        _num(cfg.get("MAX_NILS_VANNER",0)) + _num(cfg.get("MAX_NILS_FAMILJ",0))
    )
    bek_max = _num(cfg.get("MAX_BEKANTA",0))
    prod_staff = _num(cfg.get("PROD_STAFF",0))
    denominator = men_sum + kanner_sammanlagt + svarta_sum + bek_max + esk_sum + bonus_sum + prod_staff
    stats["Andel svarta (%)"] = round(100.0 * svarta_sum / denominator, 2) if denominator > 0 else 0.0

    # BM-mål / Mål vikt om angivna i cfg
    if "BM_MAL" in cfg:
        stats["BM mål (snitt)"] = round(_num(cfg["BM_MAL"]), 2)
    if "MAL_VIKT" in cfg:
        stats["Mål vikt"] = round(_num(cfg["MAL_VIKT"]), 2)

    return stats
