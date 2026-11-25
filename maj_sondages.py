import os
import re
import json
import time
import socket
import urllib.request
from datetime import datetime, timedelta, timezone

ancien_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    res = ancien_getaddrinfo(*args, **kwargs)
    return tuple(r for r in res if r.__getitem__(0) == socket.AF_INET)
socket.getaddrinfo = getaddrinfo_ipv4

STATIONS = ("07145", "07110", "07510", "07645", "07761")
os.makedirs("donnees", exist_ok=True)
infos = {}

maintenant = datetime.now(timezone.utc)
heure_pile = maintenant.replace(minute=0, second=0, microsecond=0)
creneaux = tuple(heure_pile - timedelta(hours=i) for i in range(36) if (heure_pile - timedelta(hours=i)).hour in (0, 11, 12, 23))

HOTE = ".".join(("www", "ogimet", "com"))
ROUTE = "/display_sond.php"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Referer": "https://" + HOTE + "/gsond.phtml.en"
}

for station in STATIONS:
    succes = False
    for dt in creneaux:
        url = (
            "https://" + HOTE + ROUTE +
            f"?lang=en&lugar={station}&tipo=ALL&ord=DIR&nil=NO&fmt=html"
            f"&ano={dt.year}&mes={dt.month:02d}&day={dt.day:02d}&hora={dt.hour:02d}"
        )
        try:
            time.sleep(1.5)
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=15) as rep:
                html = rep.read().decode("utf-8", errors="ignore")
                blocs = re.findall(r"<pre>(.*?)</pre>", html, re.DOTALL | re.IGNORECASE)
                texte_pre = "\n".join(blocs)

                if station == "07145" and dt == creneaux.__getitem__(0):
                    print("BLOC PRE OGIMET:", texte_pre[:600])

                lignes_csv = [
                    "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                ]
                for ligne in texte_pre.splitlines():
                    # Nettoyage des balises HTML éventuelles à l'intérieur du <pre>
                    propre = re.sub(r"<[^>]+>", " ", ligne)
                    m = propre.split()
                    if len(m) >= 7:
                        try:
                            p = float(m.pop(0))
                            h = float(m.pop(0))
                            t = float(m.pop(0))
                            td_txt = m.pop(0)
                            td = float(td_txt) if "--" not in td_txt else t
                            _rh = m.pop(0)
                            dr_txt = m.pop(0)
                            vit_txt = m.pop(0)
                            dr = float(dr_txt) if "--" not in dr_txt else float("nan")
                            # Ogimet affiche le vent en km/h dans le tableau HTML -> / 3.6 = m/s
                            vit_ms = (float(vit_txt) / 3.6) if "--" not in vit_txt else float("nan")
                            if 90 <= p <= 1050:
                                lignes_csv.append(f"{p},{h},{t},{td},{dr},{vit_ms:.1f}")
                        except ValueError:
                            continue

                if len(lignes_csv) > 15:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write("\n".join(lignes_csv))
                    infos[station] = dt.strftime("Ballon réel — %d/%m/%Y à %HZ")
                    print(f"OK Ballon réel {station} -> {infos[station]} ({len(lignes_csv)-1} niveaux)")
                    succes = True
                    break
        except Exception as e:
            print(f"Attente Ogimet {station} ({dt.strftime('%d %HZ')}) : {e}")

    if not succes:
        print(f"Aucun ballon réel trouvé pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
