import os
import re
import json
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = {
    "07145": (48.77, 2.01),   # Trappes
    "07110": (48.45, -4.41),  # Brest
    "07510": (44.83, -0.69),  # Bordeaux
    "07645": (43.86, 4.41),   # Nîmes
    "07761": (41.92, 8.80)    # Ajaccio
}

os.makedirs("donnees", exist_ok=True)
infos = {}

maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = [heure_synoptique - timedelta(hours=12 * i) for i in range(3)]

# Niveaux de pression standard pour le profil haute résolution
NIVEAUX_P = (1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100)

for station, (lat, lon) in STATIONS.items():
    succes = False
    # 1. Tentative sur le serveur européen Ogimet (ballon réel)
    for dt in creneaux:
        date_str = dt.strftime("%Y%m%d%H00")
        url_ogimet = f"https://ogimet.com{station}&tipo=ALL&ord=DIR&nil=SI&fmt=txt&ano={dt.year}&mes={dt.month:02d}&day={dt.day:02d}&hora={dt.hour:02d}"
        try:
            req = urllib.request.Request(url_ogimet, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as rep:
                texte = rep.read().decode("utf-8", errors="ignore")
                lignes_csv = [
                    "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                ]
                for ligne in texte.splitlines():
                    morceaux = ligne.split()
                    if len(morceaux) >= 7:
                        try:
                            p = float(morceaux.pop(0))
                            h = float(morceaux.pop(0))
                            t = float(morceaux.pop(0))
                            td = float(morceaux.pop(0))
                            _rh = morceaux.pop(0)
                            dr = float(morceaux.pop(0))
                            vit_kmh = float(morceaux.pop(0))
                            if 90 <= p <= 1050:
                                lignes_csv.append(f"{p},{h},{t},{td},{dr:.0f},{(vit_kmh / 3.6):.1f}")
                        except ValueError:
                            continue
                if len(lignes_csv) > 12:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = dt.strftime("Ballon réel — %d/%m/%Y %HZ")
                    print(f"OK Ogimet : {station} -> {infos[station]}")
                    succes = True
                    break
        except Exception as e:
            print(f"Ogimet {station} ({date_str}) : {e}")

    # 2. Secours ultra-rapide via Open-Meteo (profil vertical modèle si ballon absent)
    if not succes:
        try:
            vars_t = ",".join([f"temperature_{p}hPa" for p in NIVEAUX_P])
            vars_td = ",".join([f"dewpoint_{p}hPa" for p in NIVEAUX_P])
            vars_h = ",".join([f"geopotential_height_{p}hPa" for p in NIVEAUX_P])
            vars_ws = ",".join([f"windspeed_{p}hPa" for p in NIVEAUX_P])
            vars_wd = ",".join([f"winddirection_{p}hPa" for p in NIVEAUX_P])
            url_om = f"https://open-meteo.com{lat}&longitude={lon}&hourly={vars_t},{vars_td},{vars_h},{vars_ws},{vars_wd}&wind_speed_unit=ms&forecast_days=1"
            req = urllib.request.Request(url_om, headers={"User-Agent": "MeteoAssoBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as rep:
                data = json.loads(rep.read().decode("utf-8"))
                hourly = data.get("hourly", {})
                idx_h = min(maintenant.hour, len(hourly.get("time", list())) - 1)
                lignes_csv = [
                    "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                ]
                for p in NIVEAUX_P:
                    t = hourly.get(f"temperature_{p}hPa", list())[idx_h]
                    td = hourly.get(f"dewpoint_{p}hPa", list())[idx_h]
                    h = hourly.get(f"geopotential_height_{p}hPa", list())[idx_h]
                    ws = hourly.get(f"windspeed_{p}hPa", list())[idx_h]
                    wd = hourly.get(f"winddirection_{p}hPa", list())[idx_h]
                    if t is not None and h is not None:
                        lignes_csv.append(f"{p},{h},{t},{td if td is not None else t},{wd if wd is not None else 0},{ws if ws is not None else 0}")

                if len(lignes_csv) > 10:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = maintenant.strftime("Profil modèle — %d/%m/%Y %HZ")
                    print(f"OK Open-Meteo : {station} -> {infos[station]}")
        except Exception as e:
            print(f"Erreur Open-Meteo {station} : {e}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
