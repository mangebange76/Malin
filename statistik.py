# statistik.py
import math
import re
import pandas as pd

def compute_stats(df: pd.DataFrame, cfg: dict | None = None) -> dict:
    """
    Robust statistik med alias-stöd för kolumnnamn och fallback-parsning.
    Allt formateras med två decimaler (svensk decimal-komma).
    """

    stats: dict[str, str] = {}

    # ===== Hjälpare & alias =====
    cfg = cfg or {}
    LBL_PAPPAN  = cfg.get("LBL_PAPPAN",  "Pappans vänner")
    LBL_GRANNAR = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV      = cfg.get("LBL_NILS_VANNER",  "Nils vänner")
    LBL_NF      = cfg.get("LBL_NILS_FAMILJ",  "Nils familj")
    LBL_BEK     = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK     = cfg.get("LBL_ESK",     "Eskilstuna killar")

    MAX_PAPPAN  = float(cfg.get("MAX_PAPPAN", 0))
    MAX_GRANNAR = float(cfg.get("MAX_GRANNAR", 0))
    MAX_NV      = float(cfg.get("MAX_NILS_VANNER", 0))
    MAX_NF      = float(cfg.get("MAX_NILS_FAMILJ", 0))
    MAX_BEK     = float(cfg.get("MAX_BEKANTA", 0))
    PROD_STAFF  = float(cfg.get("PROD_STAFF", 0))

    # Ekonomi-aliass (för säkerhets skull)
    AL_INT_KANNER   = ["Intäkt Känner", "Intakt Känner", "Intäkt Kanner"]
    AL_KOST_MAN     = ["Kostnad män", "Kostnad man", "Kostnad män "]
    AL_INT_FORETAG  = ["Intäkt företag", "Intakt företag", "Intäkt foretag"]
    AL_LON_MALIN    = ["Lön Malin", "Lon Malin"]
    AL_VINST        = ["Vinst"]
    AL_PREN         = ["Prenumeranter"]

    # Tid per kille alias
    AL_TPK_SEK      = ["Tid per kille (sek)", "Tid/kille (sek)", "Tid per kille sek"]
    AL_HANDER_PK_SEK= ["Händer per kille (sek)", "Hander per kille (sek)"]
    AL_HANDER_AKTIV = ["Händer aktiv", "Hander aktiv"]

    # Summa-fält alias
    AL_SUM_TID_SEK  = ["Summa tid (sek)", "Summa tid sek", "Summa tid"]
    AL_SUM_D_SEK    = ["Summa D (sek)", "Summa D sek", "Summa D"]
    AL_SUM_TP_SEK   = ["Summa TP (sek)", "Summa TP sek", "Summa TP"]

    def fmt2(x: float) -> str:
        try:
            return f"{float(x):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            return "0,00"

    def fmt_pct(p: float) -> str:
        return f"{fmt2(p)} %"

    if df is None or df.empty:
        return stats

    # Normalisera kolumnnamn -> exakt uppslag
    cols_set = set(df.columns)

    def first_existing(cols: list[str]) -> str | None:
        for c in cols:
            if c in cols_set:
                return c
        return None

    def num_col(name: str) -> pd.Series:
        # enkel to_numeric med NaN->0
        return pd.to_numeric(df[name], errors="coerce").fillna(0.0)

    def num_alias(cols: list[str]) -> pd.Series:
        c = first_existing(cols)
        if c is None:
            return pd.Series([ ], dtype="float64")
        return num_col(c)

    def safe_sum_alias(cols: list[str]) -> float:
        s = num_alias(cols)
        return float(s.sum()) if len(s) else 0.0

    def sum_by_exact(name: str) -> float:
        return float(num_col(name).sum()) if name in cols_set else 0.0

    # Tolkare m:s -> sekunder
    mmss_re = re.compile(r"^\s*(\d+)\s*:\s*(\d{1,2})\s*$")
    def parse_mmss_series_if_needed(colname: str) -> pd.Series:
        # Om kolumnen finns och inte är numerisk i sekunder, försök tolka som "m:s"
        if colname not in cols_set:
            return pd.Series([], dtype="float64")
        s = df[colname]
        if pd.api.types.is_numeric_dtype(s):
            return pd.to_numeric(s, errors="coerce").fillna(0.0)
        # försök m:s
        out = []
        for val in s.fillna(""):
            if isinstance(val, (int, float)):
                out.append(float(val))
            else:
                m = mmss_re.match(str(val))
                if m:
                    mm = int(m.group(1)); ss = int(m.group(2))
                    out.append(float(mm*60 + ss))
                else:
                    out.append(0.0)
        return pd.Series(out, dtype="float64")

    # ===== Per-rad totalt män (radnivå) =====
    def totalt_man_per_rad_series() -> pd.Series:
        cols = [
            "Män", "Svarta", LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK,
            LBL_ESK, "Bonus deltagit", "Personal deltagit"
        ]
        parts = [num_col(c) if c in cols_set else pd.Series([], dtype="float64") for c in cols]
        if not parts:
            return pd.Series([], dtype="float64")
        s = parts[0]
        for p in parts[1:]:
            s = s.add(p, fill_value=0.0)
        return s

    # ===== Högst upp: GB =====
    man_col = num_col("Män") if "Män" in cols_set else pd.Series([], dtype="float64")
    antal_gb = int((man_col > 0).sum())

    privat_mask = (
        ((man_col if len(man_col) else pd.Series([0]*len(df))) == 0) &
        (
            ((num_col(LBL_PAPPAN) if LBL_PAPPAN in cols_set else 0) > 0) |
            ((num_col(LBL_GRANNAR) if LBL_GRANNAR in cols_set else 0) > 0) |
            ((num_col(LBL_NV)      if LBL_NV      in cols_set else 0) > 0) |
            ((num_col(LBL_NF)      if LBL_NF      in cols_set else 0) > 0)
        )
    )
    # om inga kolumner fanns, gör mask till falskt
    if isinstance(privat_mask, (int, float)):
        privat_mask = pd.Series([False]*len(df))
    antal_privat_gb = int(privat_mask.sum())

    stats["Antal GB"] = fmt2(antal_gb)
    stats["Privat GB"] = fmt2(antal_privat_gb)

    # ===== — TOTALER — =====
    stats["— TOTALER —"] = ""

    # Totalt antal män (statistik)
    total_man_stat = (
        sum_by_exact("Män")
        + sum_by_exact("Svarta")
        + sum_by_exact("Bonus deltagit")
        + sum_by_exact(LBL_ESK)
        + MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK + PROD_STAFF
    )
    stats["Totalt antal män (statistik)"] = fmt2(total_man_stat)

    # Andel svarta + antal för andel
    svarta = num_col("Svarta") if "Svarta" in cols_set else pd.Series([], dtype="float64")
    svart_mask = (svarta > 0) if len(svarta) else pd.Series([False]*len(df))
    andel_svarta_numerator = float(
        (svarta[svart_mask]).sum()
        + ((num_col(LBL_ESK)[svart_mask]).sum() if LBL_ESK in cols_set and len(svart_mask) else 0.0)
        + ((num_col("Bonus deltagit")[svart_mask]).sum() if "Bonus deltagit" in cols_set and len(svart_mask) else 0.0)
    )
    stats["Svarta (antal för andel)"] = fmt2(andel_svarta_numerator)
    andel_svarta = (andel_svarta_numerator / total_man_stat * 100.0) if total_man_stat > 0 else 0.0
    stats["Andel svarta"] = fmt_pct(andel_svarta)

    # Antal scener med Totalt män > 0
    total_man_per_row = totalt_man_per_rad_series()
    n_scen_totman = int((total_man_per_row > 0).sum()) if not total_man_per_row.empty else 0

    # DP/DPP/DAP/TAP (summa + snitt per scen)
    for etikett in ["DP", "DPP", "DAP", "TAP"]:
        s = sum_by_exact(etikett)
        stats[f"{etikett} (summa)"] = fmt2(s)
        stats[f"{etikett} – snitt per scen"] = ""
        stats[f"{etikett} snitt per scen"] = fmt2(s / n_scen_totman if n_scen_totman > 0 else 0.0)

    # Älskar / Sover med (summa)
    stats["Älskar (summa)"]    = fmt2(sum_by_exact("Älskar"))
    stats["Sover med (summa)"] = fmt2(sum_by_exact("Sover med"))

    # Enskilda kolumner – (summa) + (snitt per scen där kolumn > 0)
    def add_sum_and_avg_exact(col_name: str, visningsetikett: str):
        s = sum_by_exact(col_name)
        n_pos = int((num_col(col_name) > 0).sum()) if col_name in cols_set else 0
        stats[f"{visningsetikett} (summa)"] = fmt2(s)
        stats[f"{visningsetikett} – snitt per scen"] = ""
        stats[f"{visningsetikett} snitt per scen"] = fmt2(s / (n_pos if n_pos > 0 else 1))

    for nm in ["Bonus deltagit", "Personal deltagit", LBL_PAPPAN, LBL_GRANNAR, LBL_NV, LBL_NF, LBL_BEK, LBL_ESK]:
        add_sum_and_avg_exact(nm, nm)

    # Summa maxvärden (Känner)
    stats["Summa maxvärden (Känner)"] = fmt2(MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)

    # ===== — TID — =====
    stats["— TID —"] = ""

    def total_seconds_from_alias(alias_list: list[str]) -> float:
        for alt in alias_list:
            if alt in cols_set:
                return float(num_col(alt).sum())
        return 0.0

    def time_block(prefix: str, sec_total: float):
        hours = sec_total / 3600.0
        days  = sec_total / 86400.0
        weeks = sec_total / (7 * 86400.0)
        stats[f"{prefix} – timmar"] = fmt2(hours)
        stats[f"{prefix} – dagar"]  = fmt2(days)
        stats[f"{prefix} – veckor"] = fmt2(weeks)

    sum_tid_sec = total_seconds_from_alias(AL_SUM_TID_SEK)
    time_block("Summa tid", sum_tid_sec)

    sum_d_sec  = total_seconds_from_alias(AL_SUM_D_SEK)
    sum_tp_sec = total_seconds_from_alias(AL_SUM_TP_SEK)
    time_block("Summa D",  sum_d_sec)
    time_block("Summa TP", sum_tp_sec)

    # ===== — HÄNDER — =====
    stats["— HÄNDER —"] = ""
    total_rows = int(len(df))
    hander_series = num_alias(AL_HANDER_AKTIV)
    if hander_series.empty and first_existing(AL_HANDER_AKTIV):
        # fallback om kolumnen finns men inte numerisk av någon anledning
        hander_series = pd.to_numeric(df[first_existing(AL_HANDER_AKTIV)], errors="coerce").fillna(0.0)
    aktiva = int((hander_series == 1).sum()) if len(hander_series) else 0
    inaktiva = max(0, total_rows - aktiva)
    p_aktiva = (aktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    p_inaktiva = (inaktiva / total_rows * 100.0) if total_rows > 0 else 0.0
    stats["Händer aktiva (antal)"]   = fmt2(aktiva)
    stats["Händer aktiva (%)"]       = fmt_pct(p_aktiva)
    stats["Händer inaktiva (antal)"] = fmt2(inaktiva)
    stats["Händer inaktiva (%)"]     = fmt_pct(p_inaktiva)

    # ===== — EKONOMI — =====
    stats["— EKONOMI —"] = ""
    stats["Prenumeranter (summa)"]   = fmt2(safe_sum_alias(AL_PREN))
    stats["Intäkter (summa)"]        = fmt2(safe_sum_alias(["Intäkter"]))
    stats["Kostnad män (summa)"]     = fmt2(safe_sum_alias(AL_KOST_MAN))
    stats["Intäkt Känner (summa)"]   = fmt2(safe_sum_alias(AL_INT_KANNER))
    stats["Intäkt företag (summa)"]  = fmt2(safe_sum_alias(AL_INT_FORETAG))
    stats["Lön Malin (summa)"]       = fmt2(safe_sum_alias(AL_LON_MALIN))
    stats["Vinst (summa)"]           = fmt2(safe_sum_alias(AL_VINST))

    # Snitt på Lön Malin – Per scen + Per totalt män
    lon_tot = safe_sum_alias(AL_LON_MALIN)
    stats["Lön Malin / Per scen"]    = fmt2(lon_tot / (antal_gb if antal_gb > 0 else 1))
    stats["Lön Malin / Totalt män"]  = fmt2(lon_tot / (total_man_stat if total_man_stat > 0 else 1))

    # ===== — SNITT — =====
    stats["— SNITT —"] = ""

    # Snitt GB & Snitt Privat GB
    sum_totman_gb = float(total_man_per_row[man_col > 0].sum()) if not total_man_per_row.empty else 0.0
    stats["Snitt GB (Totalt män / Antal GB)"] = fmt2(sum_totman_gb / (antal_gb if antal_gb > 0 else 1))

    sum_totman_privat = float(total_man_per_row[privat_mask].sum()) if not total_man_per_row.empty else 0.0
    stats["Snitt Privat GB (Totalt män / Antal Privat GB)"] = fmt2(sum_totman_privat / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Snitt tid GB/Privat GB (h)
    sum_tid_gb_sec = float((num_col(first_existing(AL_SUM_TID_SEK) or AL_SUM_TID_SEK[0])[man_col > 0]).sum()) if first_existing(AL_SUM_TID_SEK) else 0.0
    sum_tid_privat_sec = float((num_col(first_existing(AL_SUM_TID_SEK) or AL_SUM_TID_SEK[0])[privat_mask]).sum()) if first_existing(AL_SUM_TID_SEK) else 0.0
    stats["Snitt tid GB (h)"]        = fmt2((sum_tid_gb_sec / 3600.0) / (antal_gb if antal_gb > 0 else 1))
    stats["Snitt tid Privat GB (h)"] = fmt2((sum_tid_privat_sec / 3600.0) / (antal_privat_gb if antal_privat_gb > 0 else 1))

    # Tid/kille snitt – exkl/inkl händer (min)
    # 1) Hämta TPK (sek) – alias eller parse "Tid per kille" (m:s)
    tpk_col = first_existing(AL_TPK_SEK)
    if tpk_col:
        tpk_sec = num_col(tpk_col)
    else:
        # fallback: försök tolka "Tid per kille" (m:s)
        if "Tid per kille" in cols_set:
            tpk_sec = parse_mmss_series_if_needed("Tid per kille")
        else:
            tpk_sec = pd.Series([], dtype="float64")

    # 2) Händer per kille (sek)
    hpk_col = first_existing(AL_HANDER_PK_SEK)
    hpk_sec = num_col(hpk_col) if hpk_col else pd.Series([], dtype="float64")

    # 3) Händer aktiv
    h_aktiv = num_alias(AL_HANDER_AKTIV)

    if len(tpk_sec) > 0:
        snitt_tid_ex = float(tpk_sec.mean()) / 60.0
        extra = (hpk_sec.where(h_aktiv == 1, other=0.0)).fillna(0.0) if len(hpk_sec) else 0.0
        snitt_tid_in = float((tpk_sec + (extra if isinstance(extra, pd.Series) else 0)).mean()) / 60.0
    else:
        snitt_tid_ex = 0.0
        snitt_tid_in = 0.0

    stats["Tid/kille snitt ex händer (min)"]   = fmt2(snitt_tid_ex)
    stats["Tid/kille snitt inkl händer (min)"] = fmt2(snitt_tid_in)

    # Hångel snitt (min)
    hangel_sec = num_col("Hångel (sek/kille)") if "Hångel (sek/kille)" in cols_set else pd.Series([], dtype="float64")
    snitt_hangel_min = float(hangel_sec.mean() / 60.0) if len(hangel_sec) > 0 else 0.0
    stats["Hångel snitt (min)"] = fmt2(snitt_hangel_min)

    # Älskar snitt Känner
    kanner_max_sum = (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF)
    stats["Älskar snitt Känner"] = fmt2(sum_by_exact("Älskar") / (kanner_max_sum if kanner_max_sum > 0 else 1))

    # Sover med snitt Nils familj
    stats["Sover med snitt Nils familj"] = fmt2(sum_by_exact("Sover med") / (MAX_NF if MAX_NF > 0 else 1))

    return stats
