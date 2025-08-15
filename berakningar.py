# berakningar.py
from __future__ import annotations
from datetime import datetime, timedelta, date, time

# =========================
# Hjälpfunktioner (rena)
# =========================
def _safe_int(x, default=0):
    try:
        # Tolerera strängar som "12", "12.0"
        if isinstance(x, str) and x.strip() == "":
            return default
        return int(float(x))
    except Exception:
        return default

def _calc_u(rad_in: dict) -> int:
    """
    U = Känner = Pappans vänner + Grannar + Nils vänner + Nils familj.
    """
    return (
        _safe_int(rad_in.get("Pappans vänner", 0)) +
        _safe_int(rad_in.get("Grannar", 0)) +
        _safe_int(rad_in.get("Nils vänner", 0)) +
        _safe_int(rad_in.get("Nils familj", 0))
    )

def _hm_str_from_seconds(q_sec: int) -> str:
    """Returnera t.ex. '4h 49 min' från sekunder (avrundar minuter)."""
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _ms_str_from_seconds(sec: int) -> str:
    """Returnera 'Xm Ys' från sekunder (minuter & sekunder)."""
    if sec < 0: sec = 0
    m = sec // 60
    s = sec % 60
    return f"{int(m)}m {int(s)}s"

def _age_on_date(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


# =========================================
# Huvudberäkning (används av app.py)
# =========================================
def berakna_radvarden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    """
    Utför alla radspecifika beräkningar.

    - Känner (U) = Pappans vänner + Grannar + Nils vänner + Nils familj
    - U ingår i: Summa S/D/TP/Vila
    - Älskar → +30 min per st (1800 s)
    - Sover med (0/1) → +60 min (3600 s), klampas till 0/1
    - 'Summa tid' returneras i både sekunder och 'xh y min'
    - 'Klockan' = starttid + 3h + Summa tid (h) + 1h (formaterad HH:MM)
    - 'Tid per kille' (sek) = M/Z + N/(Z*2) + O/(Z*3), Z = Män + Känner (exkl. Älskar/Sover med)
      + textformat 'Xm Ys'
    - Ekonomi enligt tidigare överenskommelser (Hångel/Suger/Prenumeranter/…/Vinst)
    - Lön Malin skalar med ålder
    """

    # Alias / indata (säkerställ int)
    c = _safe_int(rad_in.get("Män", 0))
    d = _safe_int(rad_in.get("Fitta", 0))
    e = _safe_int(rad_in.get("Rumpa", 0))
    f = _safe_int(rad_in.get("DP", 0))
    g = _safe_int(rad_in.get("DPP", 0))
    h = _safe_int(rad_in.get("DAP", 0))
    i = _safe_int(rad_in.get("TAP", 0))

    j = _safe_int(rad_in.get("Tid S", 0))  # sek
    k = _safe_int(rad_in.get("Tid D", 0))  # sek
    l = _safe_int(rad_in.get("Vila", 0))   # sek

    alskar    = _safe_int(rad_in.get("Älskar", 0))       # 30 min/st
    sover_med = _safe_int(rad_in.get("Sover med", 0))    # 0/1 → 60 min
    if sover_med < 0: sover_med = 0
    if sover_med > 1: sover_med = 1

    # U = Känner
    u = _calc_u(rad_in)

    # Summor – inkluderar U
    m = (c + d + e + u) * j                 # Summa S (sek)
    n = (f + g + h + u) * k                 # Summa D (sek)
    o = (i + u) * k                         # Summa TP (sek)
    p = (c + d + e + f + g + h + i + u) * l # Summa Vila (sek)

    # Extra tid från Älskar & Sover med
    extra_alskar_sec    = alskar * 1800     # 30 min/st
    extra_sover_med_sec = sover_med * 3600  # 60 min/st

    # Totaltid (sek + text)
    q_sec = int(m + n + o + p + extra_alskar_sec + extra_sover_med_sec)
    q_hours = q_sec / 3600.0
    summa_tid_str = _hm_str_from_seconds(q_sec)

    # Klockan (utifrån starttid)
    klockan_str = (
        datetime.combine(rad_datum, starttid)
        + timedelta(hours=3)         # +3h
        + timedelta(hours=q_hours)   # +summa tid (i timmar)
        + timedelta(hours=1)         # +1h
    ).strftime("%H:%M")

    # Totalt män Z = Män + Känner (exkl. Älskar/Sover med)
    z = int(c + u)
    z_safe = z if z > 0 else 1

    # Tid per kille (sek): M/Z + N/(Z*2) + O/(Z*3)
    if z > 0:
        tid_per_kille_sec = int(round(m / z + n / (z * 2) + o / (z * 3)))
    else:
        tid_per_kille_sec = 0
    tid_per_kille_str = _ms_str_from_seconds(tid_per_kille_sec)

    # ----- Ekonomi -----
    ac = 10800 / max(c, 1)        # Hångel (sek/kille)
    ad = (n * 0.65) / z_safe      # Suger (sek/kille) baserat på N
    ae = (c + d + e + f + g + h + i + u)  # Prenumeranter (med U)
    af = 15                       # Avgift
    ag = ae * af                  # Intäkter
    ah = c * 120                  # Intäkt män
    # Lön Malin – åldersfaktor
    ålder = _age_on_date(rad_datum, födelsedatum)
    if ålder < 18:
        raise ValueError("Ålder < 18 — spärrad rad.")
    if   18 <= ålder <= 25: faktor = 1.20
    elif 26 <= ålder <= 30: faktor = 1.10
    elif 31 <= ålder <= 40: faktor = 1.00
    else:                    faktor = 0.90
    aj_base = max(150, min(800, ae * 0.10))
    aj = max(150, min(800, aj_base * faktor))  # Lön Malin
    ai = (aj + 120) * u        # Intäkt Känner
    ak = ag * 0.20             # Intäkt Företaget
    al = ag - ah - ai - aj - ak# Vinst
    hårdhet = (2 if f > 0 else 0) + (3 if g > 0 else 0) + (5 if h > 0 else 0) + (7 if i > 0 else 0)

    # Returnera komplett resultatrad
    return {
        **rad_in,
        "Känner": u,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Tid Älskar (sek)": extra_alskar_sec,
        "Tid Älskar": _hm_str_from_seconds(extra_alskar_sec),
        "Tid Sover med (sek)": extra_sover_med_sec,
        "Tid Sover med": _hm_str_from_seconds(extra_sover_med_sec),
        "Summa tid (sek)": q_sec,
        "Summa tid": summa_tid_str,
        "Klockan": klockan_str,
        "Totalt Män": z,
        "Tid per kille (sek)": tid_per_kille_sec,
        "Tid per kille": tid_per_kille_str,  # min:sek
        # Behåll även "Tid kille" (minuter) om det används i arket:
        "Tid kille": ((m / z_safe) + (n / z_safe) + (o / z_safe) + ad) / 60,
        # Ekonomi
        "Hångel": ac,
        "Suger": ad,
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": aj,
        "Intäkt Företaget": ak,
        "Vinst": al,
        "Känner Sammanlagt": u,
        "Hårdhet": hårdhet
    }

# Alias med prickar (om någon importerar det namnet).
beräkna_radvärden = berakna_radvarden
