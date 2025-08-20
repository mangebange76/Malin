# statistik.py
import pandas as pd

def _num(s):
    try:
        return pd.to_numeric(s, errors="coerce")
    except Exception:
        return pd.Series([0])

def _col(df: pd.DataFrame, *names):
    """Försök hitta första befintliga kolumnnamnet i listan."""
    for n in names:
        if n in df.columns:
            return n
    return None

def compute_stats(rows: pd.DataFrame, cfg: dict) -> dict:
    """Beräknar robust totalsammanställning för dashboarden."""
    stats = {}

    if rows is None or len(rows) == 0:
        return stats

    df = rows.copy()

    # Säkerställ numeriska kolumner (om de finns)
    num_cols = [
        "Män","Svarta","Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Bonus deltagit","Personal deltagit",
        "Känner","Känner sammanlagt","Totalt Män",
        "Prenumeranter","Hårdhet",
        "Suger","Suger per kille (sek)","Händer per kille (sek)","Tid/kille inkl händer (sek)",
        "Summa S (sek)","Summa D (sek)","Summa TP (sek)","Summa tid (sek)",
        "Intäkter","Intäkt Känner","Intäkt företag","Kostnad män","Lön Malin","Vinst"
    ]
    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # Etiketter kan vara ändrade – mappa ”källor”
    lbl_p  = cfg.get("LBL_PAPPAN", "Pappans vänner")
    lbl_g  = cfg.get("LBL_GRANNAR", "Grannar")
    lbl_nv = cfg.get("LBL_NILS_VANNER", "Nils vänner")
    lbl_nf = cfg.get("LBL_NILS_FAMILJ", "Nils familj")
    lbl_bk = cfg.get("LBL_BEKANTA", "Bekanta")
    lbl_esk= cfg.get("LBL_ESK", "Eskilstuna killar")

    # Totalt antal rader
    stats["Totalt antal scener"] = int(len(df))

    # Summeringar (med 0 vid frånvaro)
    def ssum(col): return float(_num(df.get(col, 0)).sum())

    stats["Totalt intäkt (USD)"]         = round(ssum("Intäkter"), 2)
    stats["Totalt intäkt känner (USD)"]  = round(ssum("Intäkt Känner"), 2)
    stats["Totalt kostnad män (USD)"]    = round(ssum("Kostnad män"), 2)
    stats["Totalt intäkt företag (USD)"] = round(ssum("Intäkt företag"), 2)
    stats["Totalt lön Malin (USD)"]      = round(ssum("Lön Malin"), 2)
    stats["Totalt vinst (USD)"]          = round(ssum("Vinst"), 2)

    stats["Totalt antal prenumeranter"]  = int(ssum("Prenumeranter"))

    # Andel svarta (%) enligt din "statistik-nivå" formel
    sum_svarta = ssum("Svarta")
    sum_man    = ssum("Män")
    sum_esk    = ssum(lbl_esk)
    sum_bonus  = ssum("Bonus deltagit")

    # Känner sammanlagt = MAX-värden ur inställningar
    kanner_sammanlagt_max = (
        int(cfg.get("MAX_PAPPAN", 0))
        + int(cfg.get("MAX_GRANNAR", 0))
        + int(cfg.get("MAX_NILS_VANNER", 0))
        + int(cfg.get("MAX_NILS_FAMILJ", 0))
    )

    bekanta_max = int(cfg.get("MAX_BEKANTA", 0))
    personal_tot = int(cfg.get("PROD_STAFF", 0))

    denom = sum_man + kanner_sammanlagt_max + sum_svarta + bekanta_max + sum_esk + sum_bonus + personal_tot
    stats["Andel svarta (%)"] = round(100.0 * sum_svarta / denom, 2) if denom > 0 else 0.0

    # BM-mål och Mål vikt från cfg (om finns)
    if "BM mål" in cfg:
        stats["BM mål (snitt)"] = round(float(cfg.get("BM mål", 0)), 2)
    if "Mål vik" in cfg:
        stats["Mål vikt (kg)"] = round(float(cfg.get("Mål vik", 0)), 2)

    return stats
