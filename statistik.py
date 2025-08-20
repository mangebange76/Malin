# statistik.py
import pandas as pd

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """
    Beräknar statistik med robust typkonvertering.
    Andel svarta (%) = SUM(Svarta) / ( SUM(Män) + MAX(Känner-summan) + SUM(Svarta)
                                      + MAX(Bekanta) + SUM(Eskilstuna killar)
                                      + SUM(Bonus deltagit) + PROD_STAFF )
    """

    stats = {}
    if rows is None or len(rows) == 0:
        return stats

    df = rows.copy()

    # ---- Hjälpare ----
    def _num_series(colname: str) -> pd.Series:
        if colname not in df.columns:
            return pd.Series([], dtype="float64")
        # Gör numerisk, andra blir NaN -> 0
        return pd.to_numeric(df[colname], errors="coerce").fillna(0.0)

    def _sum(colname: str) -> float:
        return float(_num_series(colname).sum())

    def _first_existing_sum(*candidates) -> float:
        for c in candidates:
            if c in df.columns:
                return _sum(c)
        return 0.0

    # ---- Etiketter från CFG (kan vara omdöpta) ----
    lbl_pappan   = cfg.get("LBL_PAPPAN", "Pappans vänner")
    lbl_grannar  = cfg.get("LBL_GRANNAR", "Grannar")
    lbl_nv       = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    lbl_nf       = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    lbl_bek      = cfg.get("LBL_BEKANTA", "Bekanta")
    lbl_esk      = cfg.get("LBL_ESK", "Eskilstuna killar")

    # ---- Grundsummeringar ----
    stats["Totalt antal scener"]        = int(len(df))
    stats["Totalt antal prenumeranter"] = int(_sum("Prenumeranter"))

    stats["Totalt intäkt (USD)"]        = float(_first_existing_sum("Intäkter", "Intakt", "Intäkter (USD)"))
    stats["Totalt intäkt känner (USD)"] = float(_first_existing_sum("Intäkt Känner", "Intäkt känner"))
    stats["Totalt kostnad män (USD)"]   = float(_first_existing_sum("Kostnad män", "Kostnad Man"))
    stats["Totalt intäkt företag (USD)"]= float(_first_existing_sum("Intäkt företag", "Intakt företag"))
    stats["Totalt lön Malin (USD)"]     = float(_first_existing_sum("Lön Malin", "Lon Malin"))
    stats["Totalt vinst (USD)"]         = float(_first_existing_sum("Vinst"))

    # Summor för några volymer
    stats["Summa Män (kolumn)"]         = int(_sum("Män"))
    stats["Summa Svarta (kolumn)"]      = int(_sum("Svarta"))
    stats[f"Summa {lbl_esk} (kolumn)"]  = int(_sum(lbl_esk))
    stats["Summa Bonus deltagit"]       = int(_sum("Bonus deltagit"))

    # Om det finns en färdig "Totalt Män"-kolumn i raderna, summera den också
    if "Totalt Män" in df.columns:
        stats["Summa Totalt Män (kolumn)"] = int(_sum("Totalt Män"))

    # ---- Känner sammanlagt (från max-värden i inställningar) ----
    kanner_sammanlagt_max = (
        int(cfg.get("MAX_PAPPAN", 0))
        + int(cfg.get("MAX_GRANNAR", 0))
        + int(cfg.get("MAX_NILS_VANNER", 0))
        + int(cfg.get("MAX_NILS_FAMILJ", 0))
    )
    stats["Känner sammanlagt (max)"] = int(kanner_sammanlagt_max)

    # ---- Andel svarta (%) enligt din statistik-formel ----
    sum_svarta = _sum("Svarta")
    sum_man    = _sum("Män")
    sum_esk    = _sum(lbl_esk)
    sum_bonus  = _sum("Bonus deltagit")

    bekanta_max = int(cfg.get("MAX_BEKANTA", 0))
    prod_staff  = int(cfg.get("PROD_STAFF", 0))

    denom = sum_man + kanner_sammanlagt_max + sum_svarta + bekanta_max + sum_esk + sum_bonus + prod_staff
    stats["Andel svarta (%)"] = round(100.0 * sum_svarta / denom, 2) if denom > 0 else 0.0

    # ---- BM-mål & Mål vikt (om ni redan beräknat/sparat i CFG) ----
    if "BM-mål" in cfg:
        try:
            stats["BM-mål (snitt)"] = round(float(cfg["BM-mål"]), 2)
        except:
            pass
    if "Mål vikt" in cfg:
        try:
            stats["Mål vikt (kg)"] = round(float(cfg["Mål vikt"]), 1)
        except:
            pass

    # ---- Tider per kille (med händer) – medelvärden om kolumnerna finns ----
    # I liven visas Tid/kille = (Tid per kille (sek) + Händer per kille (sek)) omvandlat till mm:ss.
    # Här visar vi bara medel i sekunder som referens för statistik.
    if "Tid per kille (sek)" in df.columns:
        base_sec = _num_series("Tid per kille (sek)")
    else:
        base_sec = pd.Series([], dtype="float64")
    if "Händer per kille (sek)" in df.columns:
        hand_sec = _num_series("Händer per kille (sek)")
    else:
        hand_sec = pd.Series([], dtype="float64")

    if len(base_sec) or len(hand_sec):
        tot = (base_sec.fillna(0) + hand_sec.fillna(0))
        if len(tot):
            stats["Medel Tid/kille inkl. händer (sek)"] = round(float(tot.mean()), 2)

    return stats
