# berakningar.py
from datetime import datetime, timedelta

def _fmt_mm_ss(total_seconds: int) -> str:
    if total_seconds is None:
        return "-"
    total_seconds = max(0, int(total_seconds))
    m, s = divmod(total_seconds, 60)
    return f"{m}:{s:02d}"

def calc_row_values(grund: dict, rad_datum, fodelsedatum, starttid):
    """
    Beräknar en komplett resultatrad baserat på 'grund' + metadata.
    Förväntade nycklar i 'grund':
      - Män, Svarta, Fitta, Rumpa, DP, DPP, DAP, TAP
      - Tid S, Tid D, Vila
      - DT tid (sek/kille), DT vila (sek/kille)
      - Älskar, Sover med
      - Pappans vänner, Grannar, Nils vänner, Nils familj, Bekanta
      - Eskilstuna killar, Nils
      - Bonus deltagit, Personal deltagit
      - Känner  (summa av fyra källor)
      - Avgift, PROD_STAFF, BONUS_RATE

    Returnerar en dict med bl.a.:
      - Summa tid, Summa tid (sek), Tid per kille, Tid per kille (sek)
      - Hångel (m:s/kille), Hångel (sek/kille), Suger, Suger per kille (sek)
      - Klockan, Prenumeranter, Hårdhet, Intäkter, Intäkt Känner, Utgift män, Lön Malin, Vinst
      - Datum, Veckodag, Totalt Män, m.m.
    """
    # --- Hämta grundvärden med defensiva defaultar ---
    def g(key, default=0):
        return int(grund.get(key, default) or 0)

    def gf(key, default=0.0):
        try:
            return float(grund.get(key, default) or 0.0)
        except Exception:
            return float(default)

    # Metadata (Datum/Veckodag/Scen/Typ)
    datum_str  = grund.get("Datum") or (rad_datum.isoformat() if hasattr(rad_datum, "isoformat") else "")
    veckodag   = grund.get("Veckodag", "")
    scen       = grund.get("Scen", "")
    typ        = grund.get("Typ", "")

    # Aktörer
    man        = g("Män")
    svarta     = g("Svarta")
    esk        = g("Eskilstuna killar")
    nils       = g("Nils")
    känner     = g("Känner")  # redan summerad av appen (fyra källor)
    totalt_man = max(0, man + svarta + känner + esk + nils)

    # Tider (sek)
    tid_s      = g("Tid S")
    tid_d      = g("Tid D")
    vila       = g("Vila")
    dt_tid     = g("DT tid (sek/kille)")
    dt_vila    = g("DT vila (sek/kille)")

    # Älskar/Sover (påverkar klockan, inte "Summa tid")
    alskar     = g("Älskar")
    sover_med  = g("Sover med")

    # Ekonomi-konfig
    avgift     = gf("Avgift")
    prod_staff = int(grund.get("PROD_STAFF", 0) or 0)
    bonus_rate = float(grund.get("BONUS_RATE", 0.0) or 0.0)

    # --- Tidsberäkningar ---
    # Per kille räknar vi ihop S + D + DT-komponenterna (Vila ingår ej här)
    tid_per_kille_sec = max(0, tid_s + tid_d + dt_tid + dt_vila)
    summa_tid_sec     = tid_per_kille_sec * totalt_man

    # Presentationsvärden
    tid_per_kille_human = _fmt_mm_ss(tid_per_kille_sec)
    summa_tid_human     = _fmt_mm_ss(summa_tid_sec)

    # "Hångel" = Tid S; "Suger" = Tid D
    hangel_per_kille_sec = max(0, tid_s)
    hangel_per_kille     = _fmt_mm_ss(hangel_per_kille_sec)
    suger_tot_sec        = max(0, tid_d) * totalt_man
    suger_per_kille_sec  = max(0, tid_d)

    # Älskar på klockan
    tid_alskar_sec = max(0, alskar) * 60
    # Sov påverkar inte tiden här (okänt schema); vill du addera fast sekunder kan vi göra det senare.

    # "Klockan": starttid + summa_tid + tid_alskar
    try:
        start_dt = datetime.combine(rad_datum, starttid)
        end_dt   = start_dt + timedelta(seconds=summa_tid_sec + tid_alskar_sec)
        klockan  = end_dt.strftime("%H:%M")
    except Exception:
        klockan = "-"

    # --- Prenumeranter / Ekonomi (enkel modell, lätt att justera) ---
    # Bas: proportionalt mot Totalt Män; 1% bonus på basen via BONUS_RATE
    pren_base = totalt_man
    prenumeranter = int(round(pren_base * (1.0 + bonus_rate)))
    hardhet        = min(100, totalt_man)  # enkel proxy om du vill se ett tal 0–100

    intakter        = float(prenumeranter) * float(avgift)
    intakt_kanner   = float(känner) * float(avgift)

    # Kostnader – platshållare (säg till hur det ska vara)
    utgift_man      = 0.0
    lon_malin       = 0.0  # om du vill: prod_staff * någon sats

    vinst           = float(intakter) - float(utgift_man) - float(lon_malin)

    # --- Bygg utdata ---
    out = {}

    # Meta
    out["Datum"]      = datum_str
    out["Veckodag"]   = veckodag
    out["Scen"]       = scen
    out["Typ"]        = typ

    # Aktörer
    out["Totalt Män"] = int(totalt_man)
    out["Män"]        = man
    out["Svarta"]     = svarta
    out["Känner"]     = känner
    out["Eskilstuna killar"] = esk
    out["Nils"]       = nils

    # Tider
    out["Summa tid"]           = summa_tid_human
    out["Summa tid (sek)"]     = int(summa_tid_sec)
    out["Tid per kille"]       = tid_per_kille_human
    out["Tid per kille (sek)"] = int(tid_per_kille_sec)
    out["Klockan"]             = klockan

    out["Hångel (m:s/kille)"]  = hangel_per_kille
    out["Hångel (sek/kille)"]  = int(hangel_per_kille_sec)
    out["Suger"]               = int(suger_tot_sec)
    out["Suger per kille (sek)"] = int(suger_per_kille_sec)

    out["Tid Älskar (sek)"]    = int(tid_alskar_sec)

    # Ekonomi
    out["Prenumeranter"]   = int(prenumeranter)
    out["Hårdhet"]         = int(hardhet)
    out["Intäkter"]        = float(intakter)
    out["Intäkt Känner"]   = float(intakt_kanner)
    out["Utgift män"]      = float(utgift_man)
    out["Lön Malin"]       = float(lon_malin)
    out["Vinst"]           = float(vinst)

    # För transparens – vidarebefordra några indata också
    for key in [
        "Fitta","Rumpa","DP","DPP","DAP","TAP",
        "Tid S","Tid D","Vila",
        "DT tid (sek/kille)","DT vila (sek/kille)",
        "Älskar","Sover med",
        "Pappans vänner","Grannar","Nils vänner","Nils familj","Bekanta",
        "Bonus deltagit","Personal deltagit",
        "Avgift","PROD_STAFF","BONUS_RATE"
    ]:
        if key in grund:
            out[key] = grund[key]

    return out
