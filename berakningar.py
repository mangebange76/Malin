# berakningar.py
from datetime import datetime, timedelta, date, time

# ================== Hjälpfunktioner ==================
def _safe_int(x, default=0):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        if isinstance(x, str) and x.strip() == "":
            return default
        return float(x)
    except Exception:
        return default

def _hm_str_from_seconds(q_sec: int) -> str:
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _mmss_from_seconds(sec: int) -> str:
    m = sec // 60
    s = sec % 60
    return f"{int(m)}:{int(s):02d}"

# ================== Huvudfunktion ==================
def berakna_radvarden(grund: dict, rad_datum: date, fod: date, starttid: time) -> dict:
    """
    Tar in råvärden (grund) + radens datum + födelsedatum + starttid och returnerar
    en dict med alla fält som appen visar/lagrar.
    - Skriver inte till någon databas (det gör appen).
    """

    # ---- Läs in alla ingångar (säker konvertering) ----
    man     = _safe_int(grund.get("Män", 0))
    svarta  = _safe_int(grund.get("Svarta", 0))
    fitta   = _safe_int(grund.get("Fitta", 0))    # ej direkt använda i tid här (kan justeras senare)
    rumpa   = _safe_int(grund.get("Rumpa", 0))    # ej direkt använda i tid här
    dp      = _safe_int(grund.get("DP", 0))
    dpp     = _safe_int(grund.get("DPP", 0))
    dap     = _safe_int(grund.get("DAP", 0))
    tap     = _safe_int(grund.get("TAP", 0))

    tid_s   = _safe_int(grund.get("Tid S", 0))          # sek
    tid_d   = _safe_int(grund.get("Tid D", 0))          # sek
    vila    = _safe_int(grund.get("Vila", 0))           # sek (radens fasta vila)

    dt_tid  = _safe_int(grund.get("DT tid (sek/kille)", 0))   # sek per kille
    dt_vila = _safe_int(grund.get("DT vila (sek/kille)", 0))  # sek per kille -> ska in i Summa Vila

    alskar  = _safe_int(grund.get("Älskar", 0))
    sover   = _safe_int(grund.get("Sover med", 0))

    pappan  = _safe_int(grund.get("Pappans vänner", 0))
    grannar = _safe_int(grund.get("Grannar", 0))
    nv      = _safe_int(grund.get("Nils vänner", 0))
    nf      = _safe_int(grund.get("Nils familj", 0))
    bekanta = _safe_int(grund.get("Bekanta", 0))
    esk     = _safe_int(grund.get("Eskilstuna killar", 0))
    bonus   = _safe_int(grund.get("Bonus killar", 0))

    nils    = _safe_int(grund.get("Nils", 0))
    avgift  = _safe_float(grund.get("Avgift", 0.0))

    # ---- Totalt Män (alla källor) ----
    # Enligt dina senaste önskemål ska ALLA dessa räknas in:
    # Män + Pappans vänner + Grannar + Nils vänner + Nils familj + Bekanta + Eskilstuna killar + Bonus killar
    total_man = max(0, man + pappan + grannar + nv + nf + bekanta + esk + bonus)

    # ---- Tider per kategori ----
    # Summa S & D: enkel modell: tid per kategori * totala män
    summa_s = max(0, tid_s * total_man)
    summa_d = max(0, tid_d * total_man)

    # DT: enligt dina regler
    # - DT tid multipliceras med totalt antal män och går in i total tid (Summa tid).
    # - DT vila multipliceras med totalt antal män och ska endast gå in i Summa Vila (inte dubbelräknas).
    dt_tid_total  = max(0, dt_tid  * total_man)
    dt_vila_total = max(0, dt_vila * total_man)

    # Summa Vila: radens "Vila" (som är per rad) + DT-vila per kille * totalt antal män
    summa_vila = max(0, vila + dt_vila_total)

    # Summa TP – låter 0 (du använder DP/DPP/DAP/TAP separat i statistik)
    summa_tp = 0

    # Älskar / Sover med – tidsfält (kan fintrimmas senare om du vill andra tider)
    tid_alskar_sek = max(0, alskar * 60)     # 60s per "Älskar" – placeholder
    tid_sover_sek  = max(0, sover * 0)       # 0s nu (så att det inte förstör totals); byt t.ex. till 8h vid behov

    # Summa tid (sek): S + D + Vila + DT-tid + (ev. älskar/sover om du vill räkna in dem)
    # Vi lägger IN inte "älskar/sover" för att inte driva iväg totalen i onödan.
    # Vill du räkna in dem, lägg + tid_alskar_sek + tid_sover_sek i uttrycket.
    summa_tid_sek = max(0, summa_s + summa_d + summa_vila + dt_tid_total)

    # ---- Per kille-beräkningar ----
    tid_per_kille_sek = int(summa_tid_sek / total_man) if total_man > 0 else 0
    tid_per_kille_lbl = _ms_str_from_seconds(tid_per_kille_sek)

    # Hångel & Suger (enkla härledningar från tid per kille så att förhandsvyn är konsekvent)
    hangel_per_kille_sek = int(round(tid_per_kille_sek * 0.15))  # 15% av tiden som proxy
    suger_per_kille_sek  = int(round(tid_per_kille_sek * 0.25))  # 25% av tiden som proxy
    hangel_mmss = _mmss_from_seconds(hangel_per_kille_sek)

    # ---- Prenumeranter & ekonomi (vi håller det enkelt tills vidare) ----
    # Bonus killar ska inte påverka prenumeranter.
    prenum = max(0, _safe_int(grund.get("Känner", 0)))  # enligt tidigare: Prenumeranter = Känner
    intakter = float(prenum) * float(avgift)

    # Lön & andra fält låter vi vara neutrala nu (du sa att vi tar om dessa senare).
    intakt_man     = 0.0
    intakt_kanner  = intakter
    lon_malin      = intakter * 0.5
    intakt_foretag = intakter - lon_malin
    vinst          = intakt_foretag  # placeholder

    # ---- Klockslag (starttid + summa tid) ----
    try:
        start_dt = datetime.combine(rad_datum, starttid)
        end_dt = start_dt + timedelta(seconds=summa_tid_sek)
        klockan_str = end_dt.strftime("%H:%M")
    except Exception:
        klockan_str = "-"

    # ---- Återställnings-/visningsfält ----
    out = {}

    # Kopiera tillbaka basfält som appen skriver ut/oförändrat vill se
    out["Typ"] = grund.get("Typ", "")
    out["Veckodag"] = grund.get("Veckodag", "")
    out["Scen"] = grund.get("Scen", "")

    out["Män"] = man
    out["Svarta"] = svarta
    out["Fitta"] = fitta
    out["Rumpa"] = rumpa
    out["DP"] = dp
    out["DPP"] = dpp
    out["DAP"] = dap
    out["TAP"] = tap

    out["Tid S"] = tid_s
    out["Tid D"] = tid_d
    out["Vila"]  = vila
    out["DT tid (sek/kille)"]  = dt_tid
    out["DT vila (sek/kille)"] = dt_vila

    out["Summa S"] = summa_s
    out["Summa D"] = summa_d
    out["Summa TP"] = summa_tp
    out["Summa Vila"] = summa_vila

    out["Tid Älskar (sek)"] = tid_alskar_sek
    out["Tid Älskar"]       = _ms_str_from_seconds(tid_alskar_sek)
    out["Tid Sover med (sek)"] = tid_sover_sek
    out["Tid Sover med"]       = _hm_str_from_seconds(tid_sover_sek)

    out["Summa tid (sek)"] = summa_tid_sek
    out["Summa tid"]       = _hm_str_from_seconds(summa_tid_sek)

    out["Tid per kille (sek)"] = tid_per_kille_sek
    out["Tid per kille"]       = tid_per_kille_lbl

    out["Klockan"] = klockan_str
    out["Älskar"]  = alskar
    out["Sover med"] = sover
    out["Känner"]  = _safe_int(grund.get("Känner", 0))

    out["Pappans vänner"] = pappan
    out["Grannar"]        = grannar
    out["Nils vänner"]    = nv
    out["Nils familj"]    = nf
    out["Bekanta"]        = bekanta
    out["Eskilstuna killar"] = esk
    out["Bonus killar"]      = bonus

    out["Totalt Män"] = total_man
    out["Tid kille"]  = tid_per_kille_lbl
    out["Nils"]       = nils

    out["Hångel (sek/kille)"]   = hangel_per_kille_sek
    out["Hångel (m:s/kille)"]   = hangel_mmss

    # Suger (en totalsiffra) sätter vi som sekunder totalt = per kille * antal killar (för att fylla fältet)
    suger_total = suger_per_kille_sek * total_man
    out["Suger"] = suger_total
    out["Suger per kille (sek)"] = suger_per_kille_sek

    # Hårdhet – lämnar 0 (placeholder)
    out["Hårdhet"] = 0

    # Prenumeranter & ekonomi
    out["Prenumeranter"] = prenum
    out["Avgift"]        = avgift
    out["Intäkter"]      = intakter

    out["Intäkt män"]       = intakt_man
    out["Intäkt Känner"]    = intakt_kanner
    out["Lön Malin"]        = lon_malin
    out["Intäkt Företaget"] = intakt_foretag
    out["Vinst"]            = vinst

    # Sammanräkning Känner (kan vara samma som 'Känner' eller ackumulerad – låter radvärde = Känner)
    out["Känner Sammanlagt"] = out["Känner"]

    return out
