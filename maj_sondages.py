import os
import json
import time
import socket
import urllib.request
from datetime import datetime, timedelta, timezone

# Force IPv4 sur GitHub Actions
ancien_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    res = ancien_getaddrinfo(*args, **kwargs)
    return tuple(r for r in res if r.__getitem__(0) == socket.AF_INET)
socket.getaddrinfo = getaddrinfo_ipv4

STATIONS = ("07145", "07110", "07510", "07645", "07761")
os.makedirs("donnees", exist_ok=True)
infos = {}

# On cherche sur les 30 dernières heures pour attraper les lâchers réels (00Z, 11Z, 12Z, 23Z)
maintenant = datetime.now(timezone.utc)
heure_pile = maintenant.replace(minute=0, second=0, microsecond=0)
creneaux = tuple(heure_pile - timedelta(hours=i) for i in range(30) if (heure_pile - timedelta(hours=i)).hour in (0, 11, 12, 23))

HOTE = ".".join(("www", "ogimet", "com"))
ROUTE = "/display_sond.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
}

for station in STATIONS:
    succes = False
    for dt in creneaux:
        url = (
            "https://" + HOTE + ROUTE +
            f"?lang=en&lugar={station}&tipo=ALL&ord=DIR&nil=NO&fmt=txt"
            f"&ano={dt.year}&mes={dt.month:02d}&day={dt.day:02d}&hora={dt.hour:02d}"
        )
        try:
            time.sleep(1.0)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as rep:
                texte = rep.read().decode("utf-8", errors="ignore")
                if station == "07145" and dt == creneaux.__getitem__(0):
                print("APERCU OGIMET:", texte[:600])

                lignes_csv = [
                    "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                ]
                for ligne in texte.splitlines():
                    m = ligne.split()
                    # Format texte Ogimet : PRES HGHT TEMP DWPT RELH MIXR DRCT SKNT ...
                    if len(m) >= 8:
                        try:
                            p = float(m.pop(0))
                            h = float(m.pop(0))
                            t = float(m.pop(0))
                            td = float(m.pop(0))
                            _rh = m.pop(0)
                            _mixr = m.pop(0)
                            dr = float(m.pop(0))
                            sknt = float(m.pop(0))
                            if 90 <= p <= 1050:
                                vit_ms = sknt * 0.514444
                                lignes_csv.append(f"{p},{h},{t},{td},{dr:.0f},{vit_ms:.1f}")
                        except ValueError:
                            continue

                if len(lignes_csv) > 15:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = dt.strftime("Observation réelle — %d/%m/%Y à %HZ")
                    print(f"OK Ballon réel {station} -> {infos[station]} ({len(lignes_csv)-1} niveaux)")
                    succes = True
                    break
        except Exception as e:
            print(f"Attente Ogimet {station} ({dt.strftime('%d %HZ')}) : {e}")

    if not succes:
        print(f"Aucun ballon réel disponible récemment pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
