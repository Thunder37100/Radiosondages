import os
import json
import urllib.request
import socket

ancien_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    res = ancien_getaddrinfo(*args, **kwargs)
    return tuple(r for r in res if r.__getitem__(0) == socket.AF_INET)
socket.getaddrinfo = getaddrinfo_ipv4

from datetime import datetime, timezone

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

HOTE = ".".join(("api", "open-meteo", "com"))
ROUTE = "/v1/forecast"

for station, lat, lon in STATIONS:
    try:
        champs = list()
        for p in NIVEAUX_P:
            champs.extend((
                f"temperature_{p}hPa",
                f"dewpoint_{p}hPa",
                f"geopotential_height_{p}hPa",
                f"windspeed_{p}hPa",
                f"winddirection_{p}hPa"
            ))

        url = "https://" + HOTE + ROUTE + f"?latitude={lat}&longitude={lon}&hourly={','.join(champs)}&wind_speed_unit=ms&forecast_days=1"
        req = urllib.request.Request(url, headers={"User-Agent": "MeteoAssoBot/1.0"})

        with urllib.request.urlopen(req, timeout=15) as rep:
            data = json.loads(rep.read().decode("utf-8"))
            hourly = data.get("hourly", {})
            times = tuple(hourly.get("time", ()))
            idx_h = min(maintenant.hour, len(times) - 1)

            lignes_csv = [
                "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
            ]

            for p in NIVEAUX_P:
                t  = tuple(hourly.get(f"temperature_{p}hPa", ())). __getitem__(idx_h)
                td = tuple(hourly.get(f"dewpoint_{p}hPa", ())). __getitem__(idx_h)
                h  = tuple(hourly.get(f"geopotential_height_{p}hPa", ())). __getitem__(idx_h)
                ws = tuple(hourly.get(f"windspeed_{p}hPa", ())). __getitem__(idx_h)
                wd = tuple(hourly.get(f"winddirection_{p}hPa", ())). __getitem__(idx_h)

                if t is not None and h is not None:
                    td_val = td if td is not None else t
                    wd_val = wd if wd is not None else 0
                    ws_val = ws if ws is not None else 0
                    lignes_csv.append(f"{p},{h},{t},{td_val},{wd_val},{ws_val}")

            with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                f.write("\n".join(lignes_csv))

            infos[station] = maintenant.strftime("Profil vertical — %d/%m/%Y %HZ")
            print(f"OK {station} ({len(lignes_csv)-1} niveaux)")

    except Exception as e:
        print(f"Erreur {station}: {e}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
