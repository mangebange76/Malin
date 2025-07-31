def beräkna_radvärden(befintliga_rader, f):
    index = len(befintliga_rader)
    veckodagar = ["Lördag", "Söndag", "Måndag", "Tisdag", "Onsdag", "Torsdag", "Fredag"]
    veckodag = veckodagar[index % 7]
    scen = index

    män = f["Män"]
    fitta = f["Fitta"]
    rumpa = f["Rumpa"]
    dp = f["DP"]
    dpp = f["DPP"]
    dap = f["DAP"]
    tap = f["TAP"]
    tid_s = f["Tid S"]
    tid_d = f["Tid D"]
    vila = f["Vila"]

    summa_s = (män + fitta + rumpa) * tid_s
    summa_d = (dp + dpp + dap) * tid_d
    summa_tp = tap * tid_d
    summa_vila = (män + fitta + rumpa + dp + dpp + dap + tap) * vila
    summa_tid = (summa_s + summa_d + summa_tp + summa_vila) / 3600
    klockan = 7 + 3 + summa_tid + 1

    return [
        veckodag, scen, män, fitta, rumpa, dp, dpp, dap, tap,
        tid_s, tid_d, vila, summa_s, summa_d, summa_tp, summa_vila,
        summa_tid, klockan, f["Älskar"], f["Sover med"],
        0,  # Känner
        f["Pappans vänner"], f["Grannar"], f["Nils vänner"], f["Nils familj"],
        0, 0, f["Nils"], 10800 / max(män, 1), 0, 0, 15, 0, 0, 0, 150, 0, 0, 0
    ]
