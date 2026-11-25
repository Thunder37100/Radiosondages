import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = (
    ("07145", 48.77, 2.01),
    ("07110", 48.45, -4.41),
    ("07510", 44.83, -0.69),
    ("07645", 43.86, 4.41),
    ("07761", 41.92, 8.80)
)

NIVEAUX_P = (1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100)

os.makedirs("donnees", exist_ok=True)
infos = {}

maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = tuple(heure_synoptique - timedelta(hours=12 * i) for i in range(3))

for station, lat, lon in STATIONS:
    succes = False
    # 1. Ballon réel via Ogimet
    for dt in creneaux:
        url_og = f"https://ogimet.com{station}&tipo=ALL&ord=DIR&nil=SI&fmt=txt&ano={dt.year}&mes={dt.month:02d}&day={dt.day:02d}&hora={dt.hour:02d}"
        try:
            req = urllib.request.Request(url_og, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=8) as rep:
                texte = rep.read().decode("utf-8", errors="ignore")
                lignes_csv = ["pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"]
                for ligne in texte.splitlines():
                    m = ligne.split()
                    if len(m) >= 7:
                        try:
                            p = float(m.pop(0))
                            h = float(m.pop(0))
                            t = float(m.pop(0))
                            td = float(m.pop(0))
                            _rh = m.pop(0)
                            dr = float(m.pop(0))
                            v_kmh = float(m.pop(0))
                            if 90 <= p <= 1050:
                                lignes_csv.append(f"{p},{h},{t},{td},{dr:.0f},{(v_kmh / 3.6):.1f}")
                        except ValueError:
                            continue
                if len(lignes_csv) > 12:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = dt.strftime("Ballon réel — %d/%m/%Y %HZ")
                    print(f"OK Ogimet {station}")
                    succes = True
                    break
        except Exception as e:
            print(f"Ogimet {station}: {e}")

    # 2. Secours profil vertical haute résolution Open-Meteo
    if not succes:
        try:
            champs = list()
            for p in NIVEAUX_P:
                champs.extend((f"temperature_{p}hPa", f"dewpoint_{p}hPa", f"geopotential_height_{p}hPa", f"windspeed_{p}hPa", f"winddirection_{p}hPa"))
            url_om = f"https://open-meteo.com{lat}&longitude={lon}&hourly={','.join(champs)}&wind_speed_unit=ms&forecast_days=1"
            req = urllib.request.Request(url_om, headers={"User-Agent": "MeteoAssoBot/1.0"})
            with urllib.request.urlopen(req, timeout=10) as rep:
                data = json.loads(rep.read().decode("utf-8"))
                hourly = data.get("hourly", {})
                idx_h = min(maintenant.hour, len(hourly.get("time", list())) - 1)
                lignes_csv = ["pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"]
                for p in NIVEAUX_P:
                    liste_t = hourly.get(f"temperature_{p}hPa", list())
                    liste_td = hourly.get(f"dewpoint_{p}hPa", list())
                    liste_h = hourly.get(f"geopotential_height_{p}hPa", list())
                    liste_ws = hourly.get(f"windspeed_{p}hPa", list())
                    liste_wd = hourly.get(f"winddirection_{p}hPa", list())
                    if len(liste_h) > idx_h and liste_h.pop(idx_h) is not None:
                        pass
                # Lecture propre sans pop destructif :
                for p in NIVEAUX_P:
                    t = tuple(hourly.get(f"temperature_{p}hPa", ())). __getitem__(idx_h)
                    td = tuple(hourly.get(f"dewpoint_{p}hPa", ())). __getitem__(idx_h)
                    h = tuple(hourly.get(f"geopotential_height_{p}hPa", ())). __getitem__(idx_h)
                    ws = tuple(hourly.get(f"windspeed_{p}hPa", ())). __getitem__(idx_h)
                    wd = tuple(hourly.get(f"winddirection_{p}hPa", ())). __getitem__(idx_h)
                    if t is not None and h is not None:
                        lignes_csv.append(f"{p},{h},{t},{td if td is not None else t},{wd if wd is not None else 0},{ws if ws is not None else 0}")

                if len(lignes_csv) > 10:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = maintenant.strftime("Profil modèle — %d/%m/%Y %HZ")
                    print(f"OK Open-Meteo {station}")
        except Exception as e:
            print(f"Erreur Open-Meteo {station}: {e}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
