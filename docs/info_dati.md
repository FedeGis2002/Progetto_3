Durante la prova il simulatore espone l'ultimo campione su GET http://127.0.0.1:5005/state, sul PC del simulatore, solo mentre la simulazione è avviata. È un JSON, aggiornato ogni 100 ms. Non serve registrarsi.

I campi sono: t_s (secondi dall'avvio), speed_kmh (negativa in retromarcia), throttle e brake da 0 a 1, steer da circa -1 a 1, battery_ah, power_kw (solo trazione: in frenata resta circa 0, il recupero si vede sulla batteria), long_mps2, lat_mps2, vert_mps2, e x_m, y_m, z_m in metri della scena.

Posizione e accelerazioni sono nel riferimento del simulatore, non in lat/lon.