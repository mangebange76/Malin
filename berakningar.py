from datetime import datetime, timedelta
import pandas as pd
import random
import math

def process_lägg_till_rader(df, inst, typ, dagar, scen_tid, ov, enkel_vag, enkel_anal,
                             dp, dpp, dap, tpp, tap, tpa,
                             komp, pappans, nils_v, nils_f,
                             dt_tid_per_man, älskar, sover):

    senaste_datum = pd.to_datetime(df["Datum"].max()) if not df.empty else pd.to_datetime(inst.get("Startdatum", "2014-03-26"))
    nya_rader = []

    if typ == "Vilovecka hemma":
        # 1.5 × alla gruppers värden ska fördelas över 7 dagar (heltal)
        def fördela_grupp(gruppnamn):
            totalt = int(float(inst.get(gruppnamn, 0)) * 1.5)
            bas = totalt // 7
            extra = totalt % 7
            fördelning = [bas] * 7
            for i in random.sample(range(7), extra):
                fördelning[i] += 1
            return fördelning

        komp_dagar = fördela_grupp("Kompisar")
        pappans_dagar = fördela_grupp("Pappans vänner")
        nils_v_dagar = fördela_grupp("Nils vänner")
        nils_f_dagar = fördela_grupp("Nils familj")
        nils_sex = [0] * 7
        for i in random.sample(range(6), min(2, 6)):
            nils_sex[i] = 1

        for i in range(7):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": komp_dagar[i],
                "Pappans vänner": pappans_dagar[i],
                "Nils vänner": nils_v_dagar[i],
                "Nils familj": nils_f_dagar[i],
                "Övriga män": 0,
                "Älskar med": 8 if i < 6 else 0,
                "Sover med": 1 if i == 6 else 0,
                "Nils sex": nils_sex[i],
                "DT tid per man (sek)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
                "Scenens längd (h)": 0
            }
            nya_rader.append(rad)

    elif typ == "Vila inspelningsplats":
        for _ in range(int(dagar)):
            datum = senaste_datum + timedelta(days=1)
            senaste_datum = datum

            def slump_grupp(gruppnamn):
                maxantal = int(inst.get(gruppnamn, 0))
                return random.randint(maxantal // 4, maxantal // 2)

            rad = {
                "Datum": datum.strftime("%Y-%m-%d"),
                "Typ": typ,
                "DP": 0, "DPP": 0, "DAP": 0, "TPA": 0, "TPP": 0, "TAP": 0,
                "Enkel vaginal": 0, "Enkel anal": 0,
                "Kompisar": slump_grupp("Kompisar"),
                "Pappans vänner": slump_grupp("Pappans vänner"),
                "Nils vänner": slump_grupp("Nils vänner"),
                "Nils familj": slump_grupp("Nils familj"),
                "Övriga män": 0,
                "Älskar med": 12,
                "Sover med": 1,
                "Nils sex": 0,
                "DT tid per man (sek)": 0,
                "DT total tid (sek)": 0,
                "Total tid (sek)": 0,
                "Total tid (h)": 0,
                "Prenumeranter": 0,
                "Intäkt ($)": 0,
                "Kvinnans lön ($)": 0,
                "Mäns lön ($)": 0,
                "Kompisars lön ($)": 0,
                "Minuter per kille": 0,
                "Scenens längd (h)": 0
            }
            nya_rader.append(rad)

    else:  # Scen
        datum = senaste_datum + timedelta(days=1)

        total_män = komp + pappans + nils_v + nils_f + ov
        dt_total = dt_tid_per_man * total_män
        scen_tid_sek = scen_tid * 3600
        total_tid = scen_tid_sek + dt_total
        total_tid_h = total_tid / 3600
        min_per_kille = round((total_tid / 60) / total_män, 2) if total_män > 0 else 0

        # Prenumeranter: enkel * 1 + dubbel * 5 + trippel * 8
        dubbel = dp + dpp + dap
        trippel = tpa + tpp + tap
        prenumeranter = enkel_vag + enkel_anal + dubbel * 5 + trippel * 8
        intäkt = prenumeranter * 15

        kvinnans_lön = 100
        män_lön = (komp + pappans + nils_v + nils_f) * 200
        kvar = intäkt - kvinnans_lön - män_lön
        kompis_lön = kvar if kvar > 0 else 0

        rad = {
            "Datum": datum.strftime("%Y-%m-%d"),
            "Typ": typ,
            "DP": dp, "DPP": dpp, "DAP": dap,
            "TPA": tpa, "TPP": tpp, "TAP": tap,
            "Enkel vaginal": enkel_vag, "Enkel anal": enkel_anal,
            "Kompisar": komp, "Pappans vänner": pappans, "Nils vänner": nils_v, "Nils familj": nils_f,
            "Övriga män": ov,
            "Älskar med": älskar,
            "Sover med": sover,
            "Nils sex": 0,
            "DT tid per man (sek)": dt_tid_per_man,
            "DT total tid (sek)": dt_total,
            "Total tid (sek)": total_tid,
            "Total tid (h)": round(total_tid_h, 2),
            "Prenumeranter": prenumeranter,
            "Intäkt ($)": intäkt,
            "Kvinnans lön ($)": kvinnans_lön,
            "Mäns lön ($)": män_lön,
            "Kompisars lön ($)": kompis_lön,
            "Minuter per kille": min_per_kille,
            "Scenens längd (h)": scen_tid
        }
        nya_rader.append(rad)

    df = pd.concat([df, pd.DataFrame(nya_rader)], ignore_index=True)
    return df
