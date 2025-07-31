from datetime import datetime

def beräkna_radvärden(fält: dict, datum: str, veckodag: str, scenummer: int, ålder: int) -> list:
    # Inmatade värden
    c = fält["Män"]
    d = fält["Fitta"]
    e = fält["Rumpa"]
    f = fält["DP"]
    g = fält["DPP"]
    h = fält["DAP"]
    i = fält["TAP"]
    j = fält["Tid S"]
    k = fält["Tid D"]
    l = fält["Vila"]
    s = fält["Älskar"]
    t = fält["Sover med"]
    v = fält["Pappans vänner"]
    w = fält["Grannar"]
    x = fält["Nils vänner"]
    y = fält["Nils familj"]
    ab = fält["Nils"]
    an = fält["Prenumeranter"]
    af = fält["Avgift"]

    # Beräkningar
    m = (c + d + e) * j  # Summa S
    n = (f + g + h) * k  # Summa D
    o = i * k            # Summa TP
    p = (c + d + e + f + g + h + i) * l  # Summa Vila
    q = (m + n + o + p) / 3600  # Summa tid (timmar)
    r = 7 + 3 + q + 1  # Klockan (starttid 07 + hångel + tid + vila)
    u = v + w + x + y  # Känner
    z = max(c, 1)  # Totalt män, undviker delning med 0
    aa = ((m/z) + (n/z) + (n/z) + (o/z) + (o/z) + (o/z) + 0) / 60  # Tid kille (utan ad än)
    ac = 10800 / c if c > 0 else 0  # Hångel
    ad = (n * 0.65) / z if z > 0 else 0  # Suger
    ae = (c + d + e + f + g + h + i) * an  # Prenumeranter
    ag = ae * af  # Intäkter
    ah = c * 120  # Intäkt män
    ai = (an + 120) * u  # Intäkt känner
    # Lön Malin: 10% av pren, justerad för ålder
    prelim_lön = 0.10 * an * af
    åldersjustering = max(0.85, min(1.15, 1 - ((ålder - 18) * 0.01)))  # ex: ålder 28 → -10%
    aj = max(150, min(prelim_lön * åldersjustering, 800))  # Lön Malin
    ak = ag * 0.20  # Intäkt Företaget
    al = ag - ah - ai - aj - ak  # Vinst
    am = u  # Känner sammanlagt
    an_hårdhet = 0
    if f > 0: an_hårdhet += 2
    if g > 0: an_hårdhet += 3
    if h > 0: an_hårdhet += 5
    if i > 0: an_hårdhet += 7

    return [
        datum, veckodag, scenummer, c, d, e, f, g, h, i,
        j, k, l, m, n, o, p, q, r, s, t, u, v, w, x, y,
        c + u, aa, ab, ac, ad, an, af, ag, ah, ai, aj, ak, al, am, an_hårdhet
    ]
