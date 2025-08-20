# statistik.py
import pandas as pd

def _num_series(df: pd.DataFrame, col: str) -> pd.Series:
    """
    Hämta kolumn som numerisk serie (NaN -> 0).
    Returnerar tom float-serie om kolumnen saknas.
    """
    s = df.get(col)
    if s is None:
        return pd.Series([], dtype=float)
    return pd.to_numeric(s, errors="coerce").fillna(0.0)

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """
    Robust statistik över alla rader.
    - Klarar strängar/tomma fält i numeriska kolumner
    - Använder etiketterna i cfg (t.ex. LBL_ESK)
    - Andel svarta enligt din "statistik-nivå"-definition
    """
    stats = {}
    if rows is None or len(rows) == 0:
        return stats

    # Totalt antal scener
    stats["Antal scener"] = int(len(rows))

    # Summeringar i USD
    stats["Totalt intäkt företag (USD)"] = float(_num_series(rows, "Intäkt företag").sum())
    stats["Totalt intäkt (USD)"]         = float(_num_series(rows, "Intäkter").sum())
    stats["Totalt intäkt känner (USD)"]  = float(_num_series(rows, "Intäkt Känner").sum())
    stats["Totalt kostnad män (USD)"]    = float(_num_series(rows, "Kostnad män").sum())
    stats["Totalt lön Malin (USD)"]      = float(_num_series(rows, "Lön Malin").sum())
    stats["Totalt vinst (USD)"]          = float(_num_series(rows, "Vinst").sum())

    # Prenumeranter totalt
    stats["Totalt antal prenumeranter"]  = int(_num_series(rows, "Prenumeranter").sum())

    # Andel svarta (%)
    svarta_sum = _num_series(rows, "Svarta").sum()
    man_sum    = _num_series(rows, "Män").sum()
    esk_lbl    = cfg.get("LBL_ESK", "Eskilstuna killar")
    esk_sum    = _num_series(rows, esk_lbl).sum() if esk_lbl in rows.columns else 0.0
    bonus_sum  = _num_series(rows, "Bonus deltagit").sum()

    kanner_sammanlagt = int(cfg.get("MAX_PAPPAN", 0)) \
                      + int(cfg.get("MAX_GRANNAR", 0)) \
                      + int(cfg.get("MAX_NILS_VANNER", 0)) \
                      + int(cfg.get("MAX_NILS_FAMILJ", 0))
    bekanta_max   = int(cfg.get("MAX_BEKANTA", 0))
    personal_tot  = int(cfg.get("PROD_STAFF", 0))

    denom = man_sum + kanner_sammanlagt + svarta_sum + bekanta_max + esk_sum + bonus_sum + personal_tot
    stats["Andel svarta (%)"] = round(100.0 * svarta_sum / denom, 2) if denom > 0 else 0.0

    # Visa också Känner sammanlagt (från maxvärden)
    stats["Känner sammanlagt (inställning)"] = kanner_sammanlagt

    # BM-mål / Mål vikt om de finns i cfg
    if "BM-mål" in cfg:
        stats["BM-mål (snitt)"] = round(float(cfg["BM-mål"]), 2)
    if "Mål vikt" in cfg:
        stats["Mål vikt (kg)"] = round(float(cfg["Mål vikt"]), 2)

    return stats
