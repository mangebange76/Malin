def beräkna_radvärden(f):
    # Grundvärden
    c = f["Män"]
    d = f["Fitta"]
    e = f["Rumpa"]
    f_dp = f["DP"]
    g = f["DPP"]
    h = f["DAP"]
    i = f["TAP"]
    j = f["Tid S"]
    k = f["Tid D"]
    l = f["Vila"]
    s = f["Älskar"]
    t = f["Sover med"]
    v = f["Pappans vänner"]
    w = f["Grannar"]
    x = f["Nils vänner"]
    y = f["Nils familj"]
    z = c if c != 0 else 1  # undvik delning med noll
    an = (c + d + e + f_dp + g + h + i)
    ålder = f["Ålder"]

    # Beräkningar
    m = (c + d + e) * j                       # Summa S
    n = (f_dp + g + h) * k                    # Summa D
    o = i * k                                 # Summa TP
    p = (c + d + e + f_dp + g + h + i) * l    # Summa Vila
    q = (m + n + o + p) / 3600                # Summa tid
    r = 7 + 3 + q + 1                         # Klockan
    u = v + w + x + y                         # Känner
    aa = ((m / z) + (n / z) + (n / z) + (o / z) + (o / z) + (o / z) + 0) / 60  # Tid kille
    ac = 10800 / z                            # Hångel
    ad = (n * 0.65) / z                       # Suger
    ae = an                                   # Prenumeranter (30 dagar hanteras i framtiden)
    af = 15                                   # Avgift
    ag = ae * af                              # Intäkter
    ah = c * 120                              # Intäkt män
    ai = (120 + f.get("Nils", 0)) * u         # Intäkt känner
    aj = max(150, min(800, int(ae * 0.10)))   # Lön Malin
    # Åldersjustering av Malins lön
    if ålder < 18:
        aj = aj * 0.8
    elif ålder > 45:
        aj = aj * 0.7
    ak = ag * 0.20                            # Företagets intäkt
    al = ag - ah - ai - aj - ak              # Vinst
    am = u                                    # Känner Sammanlagt
    an_hårdhet = 0
    if f_dp > 0:
        an_hårdhet += 2
    if g > 0:
        an_hårdhet += 3
    if h > 0:
        an_hårdhet += 5
    if i > 0:
        an_hårdhet += 7

    # Sammansatt rad
    rad = {
        "Veckodag": f["Veckodag"],
        "Scen": f["Scen"],
        "Män": c,
        "Fitta": d,
        "Rumpa": e,
        "DP": f_dp,
        "DPP": g,
        "DAP": h,
        "TAP": i,
        "Tid S": j,
        "Tid D": k,
        "Vila": l,
        "Summa S": m,
        "Summa D": n,
        "Summa TP": o,
        "Summa Vila": p,
        "Summa tid": q,
        "Klockan": round(r, 2),
        "Älskar": s,
        "Sover med": t,
        "Känner": u,
        "Pappans vänner": v,
        "Grannar": w,
        "Nils vänner": x,
        "Nils familj": y,
        "Totalt Män": u + c,
        "Tid kille": round(aa, 2),
        "Nils": f.get("Nils", 0),
        "Hångel": round(ac, 2),
        "Suger": round(ad, 2),
        "Prenumeranter": ae,
        "Avgift": af,
        "Intäkter": ag,
        "Intäkt män": ah,
        "Intäkt Känner": ai,
        "Lön Malin": round(aj, 2),
        "intäkt Företaget": round(ak, 2),
        "Vinst": round(al, 2),
        "Känner Sammanlagt": am,
        "Hårdhet": an_hårdhet
    }

    return rad
