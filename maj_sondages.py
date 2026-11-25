import os
import json
import socket
import urllib.request
from datetime import datetime, timezone

# Force IPv4 sur GitHub Actions
ancien_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    res = ancien_getaddrinfo(*args, **kwargs)
    return tuple(r for r in res if r.__getitem__(0) == socket.AF_INET)
socket.getaddrinfo = getaddrinfo_ipv4

STATIONS = (
    ("07145", 48.77, 2.01, 168),   # Trappes (alt 168m)
    ("07110", 48.45, -4.41, 94),   # Brest (alt 94m)
    ("07510", 44.83, -0.69, 47),   # Bordeaux (alt 47m)
    ("07645", 43.86, 4.41, 60),    # Nîmes (alt 60m)
    ("07761", 41.92, 8.80, 5)      # Ajaccio (alt 5m)
)

NIVEAUX_P = (1000, 975, 950, 925, 900, 850, 800, 750, 700, 650, 600, 550, 500, 450, 400, 350, 300, 250, 200, 150, 100)

os.makedirs("donnees", exist_ok=True)
infos = {}
maintenant = datetime.now(timezone.utc)

HOTE = ".".join(("api", "open-meteo", "com"))
ROUTE = "/v1/forecast"

lats = ",".join(str(s.__getitem__(1)) for s in STATIONS)
lons = ",".join(str(s.__getitem__(2)) for s in STATIONS)

champs = list()
for p in NIVEAUX_P:
    champs.extend((
        f"temperature_{p}hPa",
        f"dewpoint_{p}hPa",
        f"geopotential_height_{p}hPa",
        f"windspeed_{p}hPa",
        f"winddirection_{p}hPa"
    ))

vars_surface = "temperature_2m,dew_point_2m,surface_pressure,wind_speed_10m,wind_direction_10m"
url = "https://" + HOTE + ROUTE + f"?latitude={lats}&longitude={lons}&hourly={','.join(champs)}&current={vars_surface}&wind_speed_unit=ms&forecast_days=1"

try:
    req = urllib.request.Request(url, headers={"User-Agent": "MeteoAssoBot/2.0"})
    with urllib.request.urlopen(req, timeout=30) as rep:
        liste_reponses = json.loads(rep.read().decode("utf-8"))

        for idx_st, (station, lat, lon, alt_sol) in enumerate(STATIONS):
            data = tuple(liste_reponses).__getitem__(idx_st)
            hourly = data.get("hourly", {})
            current = data.get("current", {})
            times = tuple(hourly.get("time", ()))
            idx_h = min(maintenant.hour, len(times) - 1)

            lignes_csv = [
                "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
            ]

            # 1. Ajout du vrai niveau de surface (2m / 10m)
            p_surf = current.get("surface_pressure")
            t_surf = current.get("temperature_2m")
            td_surf = current.get("dew_point_2m")
            ws_surf = current.get("wind_speed_10m")
            wd_surf = current.get("wind_direction_10m")

            if p_surf is not None and t_surf is not None:
                lignes_csv.append(f"{p_surf},{alt_sol},{t_surf},{td_surf if td_surf is not None else t_surf},{wd_surf if wd_surf is not None else 0},{ws_surf if ws_surf is not None else 0}")

            # 2. Ajout des niveaux isobares strictement au-dessus de la pression de surface
            for p in NIVEAUX_P:
                if p_surf is not None and p >= p_surf - 2:
                    continue
                t  = tuple(hourly.get(f"temperature_{p}hPa", ())). __getitem__(idx_h)
                td = tuple(hourly.get(f"dewpoint_{p}hPa", ())). __getitem__(idx_h)
                h  = tuple(hourly.get(f"geopotential_height_{p}hPa", ())). __getitem__(idx_h)
                ws = tuple(hourly.get(f"windspeed_{p}hPa", ())). __getitem__(idx_h)
                wd = tuple(hourly.get(f"winddirection_{p}hPa", ())). __getitem__(idx_h)

                if t is not None and h is not None:
                    lignes_csv.append(f"{p},{h},{t},{td if td is not None else t},{wd if wd is not None else 0},{ws if ws is not None else 0}")

            with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                f.write("\n".join(lignes_csv))

            infos[station] = maintenant.strftime("Profil vertical — %d/%m/%Y %HZ")
            print(f"OK {station} ({len(lignes_csv)-1} niveaux avec surface)")

except Exception as e:
    print(f"Erreur globale Open-Meteo : {e}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
