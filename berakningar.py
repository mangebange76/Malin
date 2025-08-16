import pandas as pd

# Hjälpfunktioner för tidshantering
def _hm_str_from_seconds(seconds: int) -> str:
    h, m = divmod(seconds // 60, 60)
    return f"{h:02d}:{m:02d}"

def _ms_from_seconds(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

# --------------------------------------------------
# Beräkna radvärden
# --------------------------------------------------
def beräkna_radvärden(rad: dict, sidopanel: dict) -> dict:
    man = int(rad.get("Män", 0))
    svarta = int(rad.get("Svarta", 0))
    bek = int(rad.get("Bekanta", 0))
    dp = int(rad.get("DP", 0))
    dpp = int(rad.get("DPP", 0))
    dap = int(rad.get("DAP", 0))
    tap = int(rad.get("TAP", 0))
    alskar = int(rad.get("Älskar", 0))
    sover_med = int(rad.get("Sover med", 0))
    dt_tid = int(rad.get("DT tid", 60))   # standard 60 sek
    dt_vila = int(rad.get("DT vila", 3))  # standard 3 sek

    # ---- Prenumeranter ----
    # Svarta ger dubbelt
    pren = man + (2 * svarta) + bek + dp + dpp + dap + tap

    # ---- Intäkter ----
    intakt_kanner = pren * 39.99
    intakt_foretag = 0  # borttaget, används nu bara som kostnad i vinst
    vinst = intakt_kanner - intakt_foretag

    # ---- Malins lön ----
    malins_lon = min(max(vinst * 0.10, 150), 800)

    # ---- Tid ----
    tid_sek = 0
    vila_sek = 0

    # DT tid & vila
    tid_sek += (man + svarta + bek) * dt_tid
    vila_sek += (man + svarta + bek) * dt_vila

    # Tid per kille (alla män + svarta + bekanta)
    total_killar = man + svarta + bek
    tid_per_kille_sek = (tid_sek // total_killar) if total_killar > 0 else 0

    # ---- Hångel (3h = 10800 sek, delas nu på män + svarta + bekanta) ----
    hangel_divisor = max(man + svarta + bek, 1)
    hangel_sek_per_kille = 10800 // hangel_divisor
    hangel_ms_per_kille  = _ms_from_seconds(hangel_sek_per_kille)

    # ---- Summera till rad ----
    rad.update({
        "Prenumeranter": pren,
        "Intäkt känner": intakt_kanner,
        "Intäkt företag": intakt_foretag,
        "Vinst": vinst,
        "Lön Malin": malins_lon,
        "Summa tid": _hm_str_from_seconds(tid_sek),
        "Summa vila": _hm_str_from_seconds(vila_sek),
        "Tid kille": _ms_from_seconds(tid_per_kille_sek),
        "Hångel (sek/kille)": hangel_ms_per_kille
    })
    return rad

# --------------------------------------------------
# Statistiksammanställning
# --------------------------------------------------
def beräkna_statistik(df: pd.DataFrame, sidopanel: dict) -> dict:
    stats = {}

    # Prenumeranter & intäkter
    stats["Aktiva prenumeranter"] = df["Prenumeranter"].sum()
    stats["Intäkt känner totalt"] = df["Intäkt känner"].sum()
    stats["Vinst totalt"] = df["Vinst"].sum()
    stats["Lön Malin totalt"] = df["Lön Malin"].sum()

    # Snitt lön Malin = lön / (män + svarta + älskar + sover med)
    divisor = (df["Män"].sum() + df["Svarta"].sum() +
               df["Älskar"].sum() + df["Sover med"].sum())
    stats["Snitt lön Malin"] = df["Lön Malin"].sum() / divisor if divisor > 0 else 0

    # Snitt tid kille per scen (där män + svarta > 0)
    scener_med_killar = df[(df["Män"] + df["Svarta"]) > 0]
    if len(scener_med_killar) > 0:
        stats["Snitt tid kille/scen"] = (
            pd.to_timedelta(scener_med_killar["Tid kille"] + ":00")
            .dt.total_seconds().mean() / 60
        )
    else:
        stats["Snitt tid kille/scen"] = 0

    # DP / DPP / DAP / TAP snitt
    for col in ["DP", "DPP", "DAP", "TAP"]:
        stats[f"Snitt {col}"] = df[col].sum() / len(df) if len(df) > 0 else 0

    # Älskar / Sover med snitt
    stats["Snitt Älskar (per max)"] = df["Älskar"].sum() / max(
        sidopanel.get("Nils familj", 1), 1
    )
    stats["Snitt Sover med (per max)"] = df["Sover med"].sum() / max(
        sidopanel.get("Nils familj", 1), 1
    )
    stats["Summa Älskar"] = df["Älskar"].sum()
    stats["Summa Sover med"] = df["Sover med"].sum()

    # Totalt antal män
    stats["Totalt män"] = df["Män"].sum() + df["Svarta"].sum()
    stats["Andel svarta (%)"] = (
        df["Svarta"].sum() / stats["Totalt män"] * 100
        if stats["Totalt män"] > 0 else 0
    )

    return stats
