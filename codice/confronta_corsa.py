"""Confronta le medie di una corsa live e di Riferimento.csv su una finestra mobile.

Legge: il JSON del simulatore e dati/corse/Riferimento.csv.
Produce: media live, media di riferimento e differenza per ogni variabile,
ricalcolate ogni PASSO_GRIGLIA_METRI metri.
Avvio: python codice/confronta_corsa.py
"""

import csv
import json
import math
import time
import urllib.error
import urllib.request
from pathlib import Path


# Modificare la cartella per confrontare la corsa con un altro riferimento.
INDIRIZZO_SIMULATORE = "http://127.0.0.1:5005/state"
FILE_RIFERIMENTO = (
    Path(__file__).resolve().parent.parent / "dati" / "corse" / "Riferimento.csv"
)
LUNGHEZZA_FINESTRA_METRI = 1000
PASSO_GRIGLIA_METRI = 1
INTERVALLO_LETTURA_SECONDI = 0.1
CAMPO_DISTANZA = "distanza_m"


def carica_riferimento(percorso):
    """Carica il CSV indicizzando le righe per distanza intera in metri."""
    if not percorso.is_file():
        raise FileNotFoundError(f"File di riferimento non trovato: {percorso}")

    riferimento = {}
    with percorso.open("r", newline="", encoding="utf-8-sig") as file_csv:
        lettore = csv.DictReader(file_csv)
        if CAMPO_DISTANZA not in (lettore.fieldnames or []):
            raise ValueError(f"Nel riferimento manca la colonna {CAMPO_DISTANZA}.")
        for riga in lettore:
            try:
                distanza = float(riga[CAMPO_DISTANZA])
            except (TypeError, ValueError):
                continue
            riferimento[round(distanza)] = riga

    if not riferimento:
        raise ValueError("Il file di riferimento non contiene distanze valide.")
    return riferimento


def leggi_campione():
    """Richiede al simulatore un campione JSON aggiornato."""
    richiesta = urllib.request.Request(
        INDIRIZZO_SIMULATORE, headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(richiesta, timeout=1) as risposta:
        campione = json.load(risposta)
    if not isinstance(campione, dict):
        raise ValueError("La risposta del simulatore non è un oggetto JSON.")
    return campione


def confronta_finestra(riferimento, campioni_live, metro_finale, variabili):
    """Confronta le medie delle misure nella finestra spaziale corrente."""
    metro_iniziale = metro_finale - LUNGHEZZA_FINESTRA_METRI
    righe_riferimento = [
        riga
        for metro, riga in riferimento.items()
        if metro_iniziale <= metro <= metro_finale
    ]
    righe_live = [
        riga
        for riga in campioni_live
        if metro_iniziale <= riga[CAMPO_DISTANZA] <= metro_finale
    ]
    risultati = {}
    for nome in variabili:
        valori_riferimento = []
        for riga in righe_riferimento:
            try:
                valori_riferimento.append(float(riga[nome]))
            except (KeyError, TypeError, ValueError):
                continue
        valori_live = []
        for riga in righe_live:
            try:
                valori_live.append(float(riga[nome]))
            except (KeyError, TypeError, ValueError):
                continue
        if not valori_riferimento or not valori_live:
            continue
        media_riferimento = sum(valori_riferimento) / len(valori_riferimento)
        media_live = sum(valori_live) / len(valori_live)
        risultati[nome] = {
            "media_riferimento": media_riferimento,
            "media_live": media_live,
            "differenza": media_live - media_riferimento,
        }
    return risultati


def main():
    if LUNGHEZZA_FINESTRA_METRI <= 0:
        raise ValueError("LUNGHEZZA_FINESTRA_METRI deve essere maggiore di zero.")
    if PASSO_GRIGLIA_METRI <= 0:
        raise ValueError("PASSO_GRIGLIA_METRI deve essere maggiore di zero.")

    riferimento = carica_riferimento(FILE_RIFERIMENTO)
    variabili = sorted(
        nome
        for nome in riferimento[next(iter(riferimento))]
        if nome not in (CAMPO_DISTANZA, "t_s")
    )
    if not variabili:
        raise ValueError("Il riferimento non contiene variabili da confrontare.")

    print(f"Riferimento caricato: {FILE_RIFERIMENTO}")
    print("Avvia il simulatore. Premi Ctrl+C per terminare il confronto.")

    distanza_corrente = 0.0
    tempo_precedente = None
    velocita_precedente = None
    prossimo_metro_confronto = LUNGHEZZA_FINESTRA_METRI
    campioni_live = []
    simulatore_attivo = False

    try:
        while True:
            inizio_attesa = time.monotonic()
            try:
                campione = leggi_campione()
                tempo = float(campione["t_s"])
                velocita = abs(float(campione["speed_kmh"])) / 3.6

                # Se il tempo torna indietro, il simulatore ha iniziato una
                # nuova corsa: si azzerano distanza e campioni precedenti.
                if tempo_precedente is not None and tempo < tempo_precedente:
                    distanza_corrente = 0.0
                    prossimo_metro_confronto = LUNGHEZZA_FINESTRA_METRI
                    campioni_live.clear()
                    velocita_precedente = None

                if tempo_precedente is not None and velocita_precedente is not None:
                    intervallo = tempo - tempo_precedente
                    if intervallo >= 0:
                        distanza_corrente += (
                            (velocita_precedente + velocita) * intervallo / 2
                        )

                # Conserva ogni misura con la sua distanza effettiva.
                campione_con_distanza = dict(campione)
                campione_con_distanza[CAMPO_DISTANZA] = distanza_corrente
                campioni_live.append(campione_con_distanza)

                # Ricalcola le medie a ogni intervallo configurato in metri.
                metro_attuale = math.floor(distanza_corrente)
                while prossimo_metro_confronto <= metro_attuale:
                    risultati = confronta_finestra(
                        riferimento, campioni_live, prossimo_metro_confronto, variabili
                    )
                    metro_iniziale = prossimo_metro_confronto - LUNGHEZZA_FINESTRA_METRI
                    riepilogo = "; ".join(
                        f"{nome}: media live={v['media_live']:.3f}, "
                        f"media riferimento={v['media_riferimento']:.3f}, "
                        f"differenza={v['differenza']:.3f}"
                        for nome, v in risultati.items()
                    ) or "nessuna misura confrontabile"
                    print(
                        f"Finestra {metro_iniziale}-{prossimo_metro_confronto} m: "
                        f"{riepilogo}"
                    )
                    prossimo_metro_confronto += PASSO_GRIGLIA_METRI

                # Mantiene i campioni utili alla prossima finestra mobile.
                limite_inferiore = max(
                    0, prossimo_metro_confronto - LUNGHEZZA_FINESTRA_METRI
                )
                campioni_live = [
                    riga for riga in campioni_live
                    if riga[CAMPO_DISTANZA] >= limite_inferiore
                ]

                tempo_precedente = tempo
                velocita_precedente = velocita
                simulatore_attivo = True

            except (urllib.error.URLError, TimeoutError, ValueError, KeyError, json.JSONDecodeError):
                if simulatore_attivo:
                    print("Simulatore non raggiungibile; attendo nuovi campioni.")
                # Evita di integrare come un solo intervallo tutto il tempo
                # trascorso mentre il simulatore non era raggiungibile.
                tempo_precedente = None
                velocita_precedente = None
                simulatore_attivo = False
                time.sleep(1)
                continue

            attesa = INTERVALLO_LETTURA_SECONDI - (time.monotonic() - inizio_attesa)
            if attesa > 0:
                time.sleep(attesa)
    except KeyboardInterrupt:
        print("Confronto terminato.")


if __name__ == "__main__":
    main()
