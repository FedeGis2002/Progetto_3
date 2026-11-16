"""Salva ogni sessione del simulatore in un CSV numerato.

Legge: GET http://127.0.0.1:5005/state (JSON descritto in docs/info_dati.md).
Produce: un file dati/simulazione_NNN.csv per ogni sessione rilevata.
Avvio: python codice/registra_simulazioni.py
"""

import csv
import json
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path


# Indirizzo del simulatore e frequenza con cui si leggono i campioni.
INDIRIZZO_SIMULATORE = "http://127.0.0.1:5005/state"
INTERVALLO_SECONDI = 0.1
CARTELLA_DATI = Path(__file__).resolve().parent.parent / "dati"
PREFISSO_FILE = "simulazione_"

# Colonne del CSV: i nomi corrispondono ai campi forniti dal simulatore,
# con in più l'ora locale in cui il campione è stato ricevuto.
CAMPI = [
    "ora_locale",
    "t_s",
    "speed_kmh",
    "throttle",
    "brake",
    "steer",
    "battery_ah",
    "power_kw",
    "long_mps2",
    "lat_mps2",
    "vert_mps2",
    "x_m",
    "y_m",
    "z_m",
]


def leggi_campione():
    """Richiede un campione e restituisce i dati JSON come dizionario."""
    richiesta = urllib.request.Request(
        INDIRIZZO_SIMULATORE, headers={"Accept": "application/json"}
    )
    with urllib.request.urlopen(richiesta, timeout=1) as risposta:
        dati = json.load(risposta)
    if not isinstance(dati, dict):
        raise ValueError("La risposta del simulatore non è un oggetto JSON.")
    return dati


def prossimo_numero_file():
    """Trova il numero più alto già usato e restituisce il successivo."""
    numeri_usati = []
    for percorso in CARTELLA_DATI.glob(f"{PREFISSO_FILE}*.csv"):
        parte_numerica = percorso.stem.removeprefix(PREFISSO_FILE)
        if parte_numerica.isdigit():
            numeri_usati.append(int(parte_numerica))
    return max(numeri_usati, default=0) + 1


def apri_file_sessione():
    """Crea il prossimo CSV numerato e scrive la riga delle intestazioni."""
    numero = prossimo_numero_file()
    percorso = CARTELLA_DATI / f"{PREFISSO_FILE}{numero:03d}.csv"

    # La modalità esclusiva evita di sovrascrivere un file, anche se esiste
    # già un file con quel nome per una modifica manuale o un avvio simultaneo.
    while True:
        try:
            file_csv = percorso.open("x", newline="", encoding="utf-8")
            break
        except FileExistsError:
            numero += 1
            percorso = CARTELLA_DATI / f"{PREFISSO_FILE}{numero:03d}.csv"

    scrittore = csv.DictWriter(file_csv, fieldnames=CAMPI)
    scrittore.writeheader()
    file_csv.flush()
    print(f"Registrazione della sessione {numero} in {percorso}")
    return file_csv, scrittore


def main():
    # Crea la cartella dati se non esiste già.
    CARTELLA_DATI.mkdir(parents=True, exist_ok=True)
    file_csv = None
    scrittore = None
    simulazione_attiva = False
    tempo_precedente = None

    print("Avvia il simulatore. Premi Ctrl+C per terminare la registrazione.")

    try:
        while True:
            inizio_attesa = time.monotonic()
            try:
                campione = leggi_campione()
                tempo = campione.get("t_s")

                # Dopo una disconnessione, oppure quando t_s torna indietro,
                # inizia una sessione e quindi un nuovo file numerato.
                tempo_azzerato = (
                    tempo is not None
                    and tempo_precedente is not None
                    and float(tempo) < float(tempo_precedente)
                )
                if not simulazione_attiva or tempo_azzerato:
                    if file_csv is not None:
                        file_csv.close()
                    file_csv, scrittore = apri_file_sessione()

                # Copia i campi noti nel CSV e lascia vuote eventuali misure
                # assenti nella risposta del simulatore.
                riga = {campo: campione.get(campo, "") for campo in CAMPI}
                riga["ora_locale"] = datetime.now().astimezone().isoformat(
                    timespec="milliseconds"
                )
                scrittore.writerow(riga)
                file_csv.flush()

                tempo_precedente = tempo
                simulazione_attiva = True

            except (urllib.error.URLError, TimeoutError, ValueError, json.JSONDecodeError):
                # Quando il simulatore si ferma, chiude il file corrente.
                # Al successivo avvio verrà creato un nuovo CSV.
                if simulazione_attiva:
                    print("Simulatore non raggiungibile: attendo il prossimo avvio.")
                if file_csv is not None:
                    file_csv.close()
                    file_csv = None
                    scrittore = None
                simulazione_attiva = False
                tempo_precedente = None
                time.sleep(1)
                continue

            # Mantiene un intervallo di circa 100 ms tra le richieste.
            attesa_rimanente = INTERVALLO_SECONDI - (time.monotonic() - inizio_attesa)
            if attesa_rimanente > 0:
                time.sleep(attesa_rimanente)
    except KeyboardInterrupt:
        print("Registrazione terminata.")
    finally:
        # Chiude il file aperto anche in caso di interruzione da tastiera.
        if file_csv is not None:
            file_csv.close()


if __name__ == "__main__":
    main()
