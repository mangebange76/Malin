# statistik.py
import pandas as pd

def compute_stats(rows_df: pd.DataFrame, cfg: dict) -> dict:
    """
    Statistik på databasnivå.
    - Alla numeriska presentationer formateras med två decimaler och komma (X,XX).
    - Procentvärden får suffixet ' %'.
    - Tidssträngar (h:mm, d/h, v/d, m:ss) lämnas som strängar.
    - SNITT-sektion läggs direkt efter Antal GB / Privat GB.
    """
    if rows_df is None or rows_df.empty:
        return {"Info": "Inga rader ännu."}

    # === Hjälpare ===
    def num(v, default=0.0):
        try:
            if v in (None, "", "NaN"):
                return float(default)
            return float(v)
        except Exception:
            return float(default)

    def sum_col(col):
        return float(rows_df[col].apply(num).sum()) if col in rows_df.columns else 0.0

    def series_col(col):
        if col in rows_df.columns:
            return rows_df[col].apply(num)
        return pd.Series([0.0] * len(rows_df))

    def count_eq(col, val):
        if col not in rows_df.columns:
            return 0
        return int((rows_df[col].apply(lambda x: int(num(x)) == val)).sum())

    def fmt_hhmm(seconds: float) -> str:
        s = max(0, int(round(seconds)))
        h, rem = divmod(s, 3600)
        m = rem // 60
        return f"{h}:{m:02d}"

    def fmt_dd_hh(seconds: float) -> str:
        s = max(0, int(round(seconds)))
        d, rem = divmod(s, 86400)
        h = rem // 3600
        return f"{d} d {h} h"

    def fmt_ww_dd(seconds: float) -> str:
        s = max(0, int(round(seconds)))
        w, rem = divmod(s, 604800)
        d = rem // 86400
        return f"{w} v {d} d"

    def fmt_mmss(seconds: float) -> str:
        s = max(0, int(round(seconds)))
        m, s = divmod(s, 60)
        return f"{m}:{s:02d}"

    def fmt2(x) -> str:
        try:
            v = float(x)
        except Exception:
            v = 0.0
        return f"{v:.2f}".replace(".", ",")

    def fmtpct(x) -> str:
        return f"{fmt2(x)} %"

    # Etiketter
    LBL_PAPPAN  = cfg.get("LBL_PAPPAN", "Pappans vänner")
    LBL_GRANNAR = cfg.get("LBL_GRANNAR", "Grannar")
    LBL_NV      = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    LBL_NF      = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    LBL_BEK     = cfg.get("LBL_BEKANTA", "Bekanta")
    LBL_ESK     = cfg.get("LBL_ESK", "Eskilstuna killar")

    # Max/inställningar
    MAX_PAPPAN = int(cfg.get("MAX_PAPPAN", 0))
    MAX_GRANNAR= int(cfg.get("MAX_GRANNAR", 0))
    MAX_NV     = int(cfg.get("MAX_NILS_VANNER", 0))
    MAX_NF     = int(cfg.get("MAX_NILS_FAMILJ", 0))
    MAX_BEK    = int(cfg.get("MAX_BEKANTA", 0))
    PROD_STAFF = int(cfg.get("PROD_STAFF", 0))

    # Serien
    man_s     = series_col("Män")
    svarta_s  = series_col("Svarta")
    bonus_s   = series_col("Bonus deltagit")
    esk_s     = series_col(LBL_ESK)
    pers_s    = series_col("Personal deltagit")
    pappan_s  = series_col(LBL_PAPPAN)
    grannar_s = series_col(LBL_GRANNAR)
    nv_s      = series_col(LBL_NV)
    nf_s      = series_col(LBL_NF)
    bek_s     = series_col(LBL_BEK)

    # GB / Privat GB
    gb_mask     = man_s > 0
    privat_mask = (man_s == 0) & ((pappan_s > 0) | (grannar_s > 0) | (nv_s > 0) | (nf_s > 0))
    gb_count    = int(gb_mask.sum())
    privat_gb   = int(privat_mask.sum())

    # Rad-total män för snitt-beräkningarna
    row_total = man_s + svarta_s + bonus_s + esk_s + pers_s + pappan_s + grannar_s + nv_s + nf_s + bek_s
    gb_total_people     = float(row_total[gb_mask].sum()) if gb_count > 0 else 0.0
    privat_total_people = float(row_total[privat_mask].sum()) if privat_gb > 0 else 0.0
    avg_gb      = (gb_total_people / gb_count) if gb_count > 0 else 0.0
    avg_priv_gb = (privat_total_people / privat_gb) if privat_gb > 0 else 0.0

    # Tid/kille snitt (med/utan händer)
    base_sec   = series_col("Tid per kille (sek)")
    hands_sec  = series_col("Händer per kille (sek)")
    hand_flag  = series_col("Händer aktiv").apply(lambda x: 1 if int(num(x))==1 else 0) if "Händer aktiv" in rows_df.columns else pd.Series([0]*len(rows_df))
    combined   = base_sec + (hands_sec * hand_flag)
    avg_no_hands   = base_sec.mean() if len(base_sec)>0 else 0.0
    avg_with_hands = combined.mean()  if len(combined)>0 else 0.0

    # Hångel snitt
    avg_kiss_sec = series_col("Hångel (sek/kille)").mean() if "Hångel (sek/kille)" in rows_df.columns else 0.0

    # === Top + SNITT-sektion (ordnad) ===
    out = {}
    out["Antal GB"]  = fmt2(gb_count)
    out["Privat GB"] = fmt2(privat_gb)

    # SNITT-sektion
    out["— SNITT —"] = ""  # visuell avdelare
    out["Snitt GB (rad-totalt män)"]        = fmt2(avg_gb)
    out["Snitt Privat GB (rad-totalt män)"] = fmt2(avg_priv_gb)
    out["Tid/kille snitt ex händer (m:s)"]  = fmt_mmss(avg_no_hands)
    out["Tid/kille snitt inkl händer (m:s)"]= fmt_mmss(avg_with_hands)
    out["Hångel – snitt (m:s/kille)"]       = fmt_mmss(avg_kiss_sec)

    # === Resten av statistiken ===
    # Totalt män (stat)
    total_man = (
        float(man_s.sum()) +
        float(svarta_s.sum()) +
        float(bonus_s.sum()) +
        float(esk_s.sum()) +
        MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF + MAX_BEK + PROD_STAFF
    )
    out["Totalt män (stat)"] = fmt2(total_man)

    # Andel svarta (%): (Svarta + Esk + Bonus) på rader där Svarta>0, delat på Totalt män (stat)
    mask_black_rows = svarta_s > 0
    svarta_total_for_stat = float(svarta_s[mask_black_rows].sum() + esk_s[mask_black_rows].sum() + bonus_s[mask_black_rows].sum()) if mask_black_rows.any() else 0.0
    andel_svarta = (svarta_total_for_stat / total_man * 100.0) if total_man > 0 else 0.0
    out["Andel svarta (%)"] = fmtpct(andel_svarta)

    # DP/DPP/DAP/TAP totalsummor
    for col in ["DP", "DPP", "DAP", "TAP"]:
        out[f"Summa {col}"] = fmt2(sum_col(col))

    # Älskar / Sover med
    total_alskar = sum_col("Älskar")
    total_sover  = sum_col("Sover med")
    out["Älskar (antal) – totalt"]    = fmt2(total_alskar)
    out["Sover med (antal) – totalt"] = fmt2(total_sover)
    denom_nf = MAX_NF if MAX_NF > 0 else 1
    out["Sover med / MAX Nils familj"] = fmt2(total_sover / float(denom_nf))

    # Enskilda källfält – totalsummor
    out[f"Summa {LBL_PAPPAN}"]  = fmt2(float(pappan_s.sum()))
    out[f"Summa {LBL_GRANNAR}"] = fmt2(float(grannar_s.sum()))
    out[f"Summa {LBL_NV}"]      = fmt2(float(nv_s.sum()))
    out[f"Summa {LBL_NF}"]      = fmt2(float(nf_s.sum()))
    out[f"Summa {LBL_BEK}"]     = fmt2(float(bek_s.sum()))
    out["Summa Bonus deltagit"]   = fmt2(float(bonus_s.sum()))
    out["Summa Personal deltagit"]= fmt2(float(pers_s.sum()))
    out[f"Summa {LBL_ESK}"]       = fmt2(float(esk_s.sum()))

    # Summa tid (sek) och varianter
    sum_tid_sec = sum_col("Summa tid (sek)")
    out["Summa tid (sek) – totalt"]   = fmt2(sum_tid_sec)
    out["Summa tid – timmar:minuter"] = fmt_hhmm(sum_tid_sec)
    out["Summa tid – dagar/timmar"]   = fmt_dd_hh(sum_tid_sec)
    out["Summa tid – veckor/dagar"]   = fmt_ww_dd(sum_tid_sec)

    # Summa D (sek) och Summa TP (sek) + formateringar
    sum_d_sec  = sum_col("Summa D (sek)")
    sum_tp_sec = sum_col("Summa TP (sek)")
    out["Summa D (sek) – totalt"]     = fmt2(sum_d_sec)
    out["Summa D – timmar:minuter"]   = fmt_hhmm(sum_d_sec)
    out["Summa D – dagar/timmar"]     = fmt_dd_hh(sum_d_sec)
    out["Summa D – veckor/dagar"]     = fmt_ww_dd(sum_d_sec)

    out["Summa TP (sek) – totalt"]    = fmt2(sum_tp_sec)
    out["Summa TP – timmar:minuter"]  = fmt_hhmm(sum_tp_sec)
    out["Summa TP – dagar/timmar"]    = fmt_dd_hh(sum_tp_sec)
    out["Summa TP – veckor/dagar"]    = fmt_ww_dd(sum_tp_sec)

    # Händer aktiv/inaktiv
    total_rows = len(rows_df)
    aktiva   = count_eq("Händer aktiv", 1)
    inaktiva = count_eq("Händer aktiv", 0)
    out["Händer aktiv – antal"]   = fmt2(aktiva)
    out["Händer inaktiv – antal"] = fmt2(inaktiva)
    out["Händer aktiv – %"]       = fmtpct((aktiva/total_rows)*100.0 if total_rows>0 else 0.0)
    out["Händer inaktiv – %"]     = fmtpct((inaktiva/total_rows)*100.0 if total_rows>0 else 0.0)

    # Summa maxvärden (4 fält)
    summa_max_kallor = MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF
    out["Summa maxvärden (Pappan+Grannar+Nils vänner+Nils familj)"] = fmt2(summa_max_kallor)

    # Tid Älskar totals + kvot mot summa max
    tot_alskar_sec = sum_col("Tid Älskar (sek)")
    out["Tid Älskar (sek) – totalt"]   = fmt2(tot_alskar_sec)
    out["Tid Älskar – timmar:minuter"] = fmt_hhmm(tot_alskar_sec)
    denom_summa_max = (MAX_PAPPAN + MAX_GRANNAR + MAX_NV + MAX_NF) or 1
    out["Tid Älskar / (summa max 4 fält)"] = fmt2(tot_alskar_sec / float(denom_summa_max))

    return out
