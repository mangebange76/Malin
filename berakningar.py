from datetime import datetime, timedelta, date, time

# =========================
# Hjälpfunktioner (rena)
# =========================
def _safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def _calc_u(rad_in: dict) -> int:
    """U = Känner = Pappans vänner + Grannar + Nils vänner + Nils familj."""
    return (
        _safe_int(rad_in.get("Pappans vänner", 0)) +
        _safe_int(rad_in.get("Grannar", 0)) +
        _safe_int(rad_in.get("Nils vänner", 0)) +
        _safe_int(rad_in.get("Nils familj", 0))
    )

def _hm_str_from_seconds(q_sec: int) -> str:
    """Returnera t.ex. '4h 49 min'."""
    h = q_sec // 3600
    m = round((q_sec % 3600) / 60)
    if m == 60:
        h += 1
        m = 0
    return f"{int(h)}h {int(m)} min"

def _age_on_date(d: date, birth: date) -> int:
    return d.year - birth.year - ((d.month, d.day) < (birth.month, birth.day))


# =========================================
# Huvudfunktion (används av app.py)
# =========================================
def beräkna_radvärden(rad_in: dict, rad_datum: date, födelsedatum: date, starttid: time) -> dict:
    """
    Beräkna alla radfält enligt överenskommen logik.
    - Inkluderar U (Känner) i M (Summa S), N (Summa D), O (Summa TP) och P (Summa Vila).
    - AE (Prenumeranter) inkluderar också U (enl. “Ja”).
    - Summa tid i 'xh y min' samt sparar 'Summa tid (sek)'.
    - Klockan: 7 + 3 + q + 1 → visas HH:MM.
    - Lön Malin har åldersfaktor.
    """

    # Indata (säkra int)
    c = _safe_int(rad_in.get("Män", 0))
    d = _safe_int(rad_in.get("Fitta", 0))
    e = _safe_int(rad_in.get("Rumpa", 0))
    f = _safe_int(rad_in.get("DP", 0))
    g = _safe_int(rad_in.get("DPP", 0))
    h = _safe_int(rad_in.get("DAP", 0))
    i = _safe_int(rad_in.get("TAP", 0))

    j = _safe_int(rad_in.get("Tid S", 0))
    k = _safe_int(rad_in.get("Tid D", 0))
    l = _safe_int(rad_in.get("Vila", 0))

    # U = Känner
    u = _calc_u(rad_in)

    # Summor (inkluderar U i M, N, O, P enligt ditt “Ja”)
    m = (c + d + e + u) * j                 # Summa S
    n = (f + g + h + u) * k                 # Summa D
    o = (i + u) * k                         # Summa TP
    p = (c + d + e + f + g + h + i + u) * l # Summa Vila

    q_sec = m + n + o + p
    q_hours = q_sec / 3600.0

    # Klockan: (7 + 3 + q + 1) → visa HH:MM
    klockan_str = (
        datetime.combine(rad_datum, starttid)
        + timedelta(hours=3) + timedelta(hours=q_hours) + timedelta(hours=1)
    ).strftime("%H:%M")

    # Summa tid som text
    summa_tid_str = _hm_str_from_seconds(q_sec)

    # Övrigt
    z = u + c
    z_safe = z if z > 0 else 1
    ac = 10800 / max(c, 1)       # Hångel
    ad = (n * 0.65) / z_safe     # Suger
    ae = (c + d + e + f + g + h + i + u)  # Prenumeranter (NU MED U)
    af = 15
    ag = ae * af
    ah = c * 120

    # Lön Malin – ålder & faktor
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

    return {
        **rad_in,
        "Summa S": m, "Summa D": n, "Summa TP": o, "Summa Vila": p,
        "Summa tid": summa_tid_str, "Summa tid (sek)": q_sec,
        "Klockan": klockan_str, "Känner": u, "Totalt Män": z,
        "Tid kille": ((m / z_safe) + (n / z_safe) + (o / z_safe) + ad) / 60,
        "Hångel": ac, "Suger": ad, "Prenumeranter": ae, "Avgift": af, "Intäkter": ag,
        "Intäkt män": ah, "Intäkt Känner": ai, "Lön Malin": aj, "Intäkt Företaget": ak,
        "Vinst": al, "Känner Sammanlagt": u, "Hårdhet": hårdhet
    }
