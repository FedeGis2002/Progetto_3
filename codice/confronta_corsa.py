"""Confronta una corsa live con Riferimento.csv su una finestra mobile.

Legge: il JSON del simulatore e dati/corse/Riferimento.csv.
Produce: le differenze per variabile a ogni metro percorso. Il valore singolo
che riassume le differenze è lasciato da definire in combina_differenze().
Avvio: python codice/confronta_corsa.py
"""

import csv
import json
import math
import time
import urllib.error
import urllib.request
from bisect import bisect_left
from pathlib import Path


# Modificare la cartella per confrontare la corsa con un altro riferimento.
INDIRIZZO_SIMULATORE = "http://127.0.0.1:5005/state"
FILE_RIFERIMENTO = (
    Path(__file__).resolve().parent.parent / "dati" / "corse" / "Riferimento.csv"
)
LUNGHEZZA_FINESTRA_METRI = 1000
PASSO_GRIGLIA_METRI = 1
INTERVALLO_LETTURA_SECONDI = 0.1


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


CAMPO_DISTANZA = "distanza_m"


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


def combina_differenze(differenze):
    """Punto da completare quando sarà definita la formula del valore singolo.

    Riceve un dizionario: nome variabile -> lista di coppie
    (distanza in metri, valore live meno valore di riferimento).
    """
    return None


def confronta_finestra(riferimento, campioni_live, metro_finale, variabili):
    """Confronta i campioni nelle ultime 1000 posizioni della griglia."""
    metro_iniziale = metro_finale - LUNGHEZZA_FINESTRA_METRI
    differenze = {nome: [] for nome in variabili}
    metri_disponibili = sorted(
        metro
        for metro in campioni_live
        if metro_iniziale <= metro <= metro_finale
    )
    if not metri_disponibili:
        return differenze

    for metro in range(metro_iniziale, metro_finale + 1, PASSO_GRIGLIA_METRI):
        riga_riferimento = riferimento.get(metro)
        if riga_riferimento is None:
            continue

        # Cerca il campione live più vicino al metro richiesto, usando soltanto
        # misure già acquisite nella finestra. La ricerca binaria evita di
        # scandire tutti i campioni a ogni metro.
        posizione = bisect_left(metri_disponibili, metro)
        indici = [
            indice
            for indice in (posizione - 1, posizione)
            if 0 <= indice < len(metri_disponibili)
        ]
        metro_live = min(
            (metri_disponibili[indice] for indice in indici),
            key=lambda valore: abs(valore - metro),
        )
        riga_live = campioni_live[metro_live]

        for nome in variabili:
            try:
                valore_live = float(riga_live[nome])
                valore_riferimento = float(riga_riferimento[nome])
            except (KeyError, TypeError, ValueError):
                continue
            differenze[nome].append((metro, valore_live - valore_riferimento))

    return differenze


def main():
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
    ultimo_metro_confrontato = LUNGHEZZA_FINESTRA_METRI - 1
    campioni_live = {}
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
                    ultimo_metro_confrontato = LUNGHEZZA_FINESTRA_METRI - 1
                    campioni_live.clear()
                    velocita_precedente = None

                if tempo_precedente is not None and velocita_precedente is not None:
                    intervallo = tempo - tempo_precedente
                    if intervallo >= 0:
                        distanza_corrente += (
                            (velocita_precedente + velocita) * intervallo / 2
                        )

                # Conserva i campioni live sulla griglia di distanza al metro.
                metro_campione = round(distanza_corrente)
                campione_con_distanza = dict(campione)
                campione_con_distanza[CAMPO_DISTANZA] = distanza_corrente
                campioni_live[metro_campione] = campione_con_distanza

                # Appena viene raggiunto un nuovo metro, aggiorna il confronto.
                metro_attuale = math.floor(distanza_corrente)
                while ultimo_metro_confrontato < metro_attuale:
                    ultimo_metro_confrontato += PASSO_GRIGLIA_METRI
                    if ultimo_metro_confrontato < LUNGHEZZA_FINESTRA_METRI:
                        continue

                    differenze = confronta_finestra(
                        riferimento,
                        campioni_live,
                        ultimo_metro_confrontato,
                        variabili,
                    )
                    valore_singolo = combina_differenze(differenze)
                    quantita = sum(len(valori) for valori in differenze.values())
                    metro_iniziale = (
                        ultimo_metro_confrontato - LUNGHEZZA_FINESTRA_METRI
                    )
                    risultato = (
                        "da definire"
                        if valore_singolo is None
                        else str(valore_singolo)
                    )
                    print(
                        f"Finestra {metro_iniziale}-{ultimo_metro_confrontato} m: "
                        f"{quantita} differenze disponibili; valore combinato: {risultato}"
                    )

                # Elimina i campioni più vecchi di quelli necessari alla
                # finestra corrente, mantenendo un margine di un metro.
                limite_inferiore = max(
                    0,
                    ultimo_metro_confrontato - LUNGHEZZA_FINESTRA_METRI - 1,
                )
                campioni_live = {
                    metro: riga
                    for metro, riga in campioni_live.items()
                    if metro >= limite_inferiore
                }

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
