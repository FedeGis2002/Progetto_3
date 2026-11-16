"""Carica le corse, calcola la distanza e salva la corsa media.

Legge: file CSV nella cartella indicata da CARTELLA_CORSE, dentro dati/.
Aggiorna: ogni CSV sorgente aggiungendo distanza_m subito dopo t_s.
Produce: Riferimento.csv, con le variabili mediate a intervalli di distanza.
Avvio: python codice/leggi_simulazioni.py
"""

import csv
from pathlib import Path


# Cambia questo nome per selezionare una cartella diversa dentro dati/.
CARTELLA_DATI = Path(__file__).resolve().parent.parent / "dati"
CARTELLA_CORSE = CARTELLA_DATI / "corse"
FILE_RIFERIMENTO = CARTELLA_CORSE / "Riferimento.csv"

# Distanza tra due punti successivi della corsa media, espressa in metri.
PASSO_DISTANZA_METRI = 1.0
CAMPO_DISTANZA = "distanza_m"


def leggi_file_csv(percorso):
    """Legge un CSV e restituisce le righe come dizionari."""
    with percorso.open("r", newline="", encoding="utf-8-sig") as file_csv:
        lettore = csv.DictReader(file_csv)
        intestazioni = lettore.fieldnames or []
        return intestazioni, list(lettore)


def aggiungi_distanza(righe):
    """Calcola la distanza cumulata integrando la velocità tra i campioni."""
    tempo_precedente = None
    velocita_precedente = None
    distanza = 0.0

    for riga in righe:
        try:
            tempo = float(riga["t_s"])
            # Il valore assoluto fa crescere la distanza anche in retromarcia.
            velocita = abs(float(riga["speed_kmh"])) / 3.6
        except (KeyError, TypeError, ValueError):
            riga[CAMPO_DISTANZA] = ""
            continue

        if tempo_precedente is not None and tempo >= tempo_precedente:
            intervallo = tempo - tempo_precedente
            # Regola dei trapezi: usa la velocità media tra i due campioni.
            distanza += (velocita_precedente + velocita) * intervallo / 2

        riga[CAMPO_DISTANZA] = distanza
        tempo_precedente = tempo
        velocita_precedente = velocita

    return righe


def scrivi_csv_corsa(percorso, intestazioni, righe):
    """Riscrive il CSV sorgente inserendo distanza_m subito dopo t_s."""
    intestazioni = [nome for nome in intestazioni if nome != CAMPO_DISTANZA]
    if "t_s" in intestazioni:
        posizione = intestazioni.index("t_s") + 1
    else:
        posizione = 0
    intestazioni.insert(posizione, CAMPO_DISTANZA)

    with percorso.open("w", newline="", encoding="utf-8") as file_csv:
        scrittore = csv.DictWriter(file_csv, fieldnames=intestazioni)
        scrittore.writeheader()
        scrittore.writerows(righe)


def leggi_tutte_le_corse(cartella):
    """Legge le corse, aggiunge la distanza e aggiorna i relativi CSV."""
    if not cartella.is_dir():
        raise FileNotFoundError(
            f"La cartella delle corse non esiste: {cartella}\n"
            "Creala dentro dati/ oppure modifica CARTELLA_CORSE nel programma."
        )

    corse = {}
    for percorso in sorted(cartella.glob("*.csv")):
        # Il riferimento prodotto in precedenza non è una corsa di origine.
        if percorso.resolve() == FILE_RIFERIMENTO.resolve():
            continue

        intestazioni, righe = leggi_file_csv(percorso)
        aggiungi_distanza(righe)
        scrivi_csv_corsa(percorso, intestazioni, righe)
        corse[percorso.name] = righe

    return corse


def campioni_per_distanza(righe):
    """Ordina i campioni per distanza e gestisce i tratti a velocità zero."""
    campioni = []
    for riga in righe:
        try:
            distanza = float(riga[CAMPO_DISTANZA])
        except (KeyError, TypeError, ValueError):
            continue

        # Se la distanza è ripetuta (per esempio a veicolo fermo), conserva
        # l'ultimo campione raggiunto a quella posizione.
        if campioni and distanza == campioni[-1][0]:
            campioni[-1] = (distanza, riga)
        else:
            campioni.append((distanza, riga))

    return campioni


def valore_campione_piu_vicino(campioni, distanza, variabile):
    """Restituisce il valore acquisito al campione più vicino alla distanza."""
    if not campioni or distanza < campioni[0][0] or distanza > campioni[-1][0]:
        return None

    # Usa direttamente una misura registrata, senza stimarla tra due campioni.
    _, riga = min(campioni, key=lambda campione: abs(campione[0] - distanza))
    try:
        return float(riga[variabile])
    except (KeyError, TypeError, ValueError):
        return None


def calcola_corsa_media(corse):
    """Calcola la media delle variabili numeriche a distanze comuni."""
    campioni_corse = [campioni_per_distanza(righe) for righe in corse.values()]
    campioni_corse = [campioni for campioni in campioni_corse if campioni]
    if not campioni_corse:
        return []

    variabili = set()
    for righe in corse.values():
        for riga in righe:
            for nome, valore in riga.items():
                if nome in ("ora_locale", "t_s", CAMPO_DISTANZA) or valore in (None, ""):
                    continue
                try:
                    float(valore)
                except (TypeError, ValueError):
                    continue
                variabili.add(nome)

    # La griglia comune parte da zero e avanza del passo configurato. Si
    # aggiunge anche la distanza massima se non coincide con un passo intero.
    distanza_massima = max(campioni[-1][0] for campioni in campioni_corse)
    if PASSO_DISTANZA_METRI <= 0:
        raise ValueError("PASSO_DISTANZA_METRI deve essere maggiore di zero.")
    numero_passi = int(distanza_massima // PASSO_DISTANZA_METRI)
    distanze = [passo * PASSO_DISTANZA_METRI for passo in range(numero_passi + 1)]
    if not distanze or distanze[-1] < distanza_massima:
        distanze.append(distanza_massima)

    corsa_media = []
    for distanza in distanze:
        riga_media = {CAMPO_DISTANZA: distanza}
        for variabile in sorted(variabili):
            valori = []
            for campioni in campioni_corse:
                valore = valore_campione_piu_vicino(campioni, distanza, variabile)
                if valore is not None:
                    valori.append(valore)
            # Ogni misura usa le corse che coprono quella distanza.
            riga_media[variabile] = sum(valori) / len(valori) if valori else ""
        corsa_media.append(riga_media)

    return corsa_media


def main():
    # Carica i CSV selezionati, aggiunge la distanza e calcola il riferimento.
    corse = leggi_tutte_le_corse(CARTELLA_CORSE)
    if not corse:
        print(f"Nessun file CSV di corsa trovato in {CARTELLA_CORSE}")
        return

    corsa_media = calcola_corsa_media(corse)
    if not corsa_media:
        print("Nessun campione valido con tempo e velocità disponibili.")
        return

    # Nel riferimento la distanza è l'asse di confronto; t_s resta solo nei
    # file delle corse originali e non viene mediato né scritto qui.
    variabili = sorted(nome for nome in corsa_media[0] if nome not in ("t_s", CAMPO_DISTANZA))
    colonne = [CAMPO_DISTANZA] + variabili
    with FILE_RIFERIMENTO.open("w", newline="", encoding="utf-8") as file_csv:
        scrittore = csv.DictWriter(file_csv, fieldnames=colonne)
        scrittore.writeheader()
        scrittore.writerows(corsa_media)
    print(f"Corsa media salvata in {FILE_RIFERIMENTO}")


if __name__ == "__main__":
    main()
