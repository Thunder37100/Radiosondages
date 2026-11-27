import os
import json
import time
import socket
import urllib.request
import http.cookiejar
from datetime import datetime, timedelta, timezone

ancien_getaddrinfo = socket.getaddrinfo
def getaddrinfo_ipv4(*args, **kwargs):
    res = ancien_getaddrinfo(*args, **kwargs)
    return tuple(r for r in res if r.__getitem__(0) == socket.AF_INET)
socket.getaddrinfo = getaddrinfo_ipv4

STATIONS = ("07145", "07110", "07510", "07761")
os.makedirs("donnees", exist_ok=True)

infos = {}
if os.path.exists("donnees/infos.json"):
    try:
        with open("donnees/infos.json", "r", encoding="utf-8") as f:
            infos = json.load(f)
    except Exception:
        infos = {}

cookies = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookies))
HOTE = ".".join(("weather", "uwyo", "edu"))

opener.addheaders = [
    ("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"),
    ("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,text/csv,*/*;q=0.8"),
    ("Accept-Language", "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7"),
    ("Referer", "https://" + HOTE + "/upperair/bufrraob.shtml"),
    ("Connection", "keep-alive")
]

try:
    opener.open("https://" + HOTE + "/upperair/bufrraob.shtml", timeout=15).read()
    time.sleep(3)
except Exception as e:
    print(f"Init session Wyoming : {e}")

maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = tuple(heure_synoptique - timedelta(hours=12 * i) for i in range(2))

for idx, station in enumerate(STATIONS):
    if idx == 3:
        print("Pause de 65 secondes pour réinitialiser le quota serveur...")
        time.sleep(65.0)

    succes = False
    for dt in creneaux:
        date_url = dt.strftime("%Y-%m-%d%%20%H:00:00")
        url = "https://" + HOTE + f"/wsgi/sounding?datetime={date_url}&id={station}&type=TEXT:CSV&src=BUFR"

        for essai in range(3):
            try:
                time.sleep(4.0)
                with opener.open(url, timeout=25) as rep:
                    texte = rep.read().decode("utf-8", errors="ignore").strip()
                    if "pressure_hPa" in texte and len(texte.splitlines()) > 15:
                        with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                            f.write(texte)
                        infos[station] = dt.strftime("Observation réelle — %d/%m/%Y à %HZ")
                        print(f"OK Ballon réel {station} -> {infos[station]} ({len(texte.splitlines())-1} niveaux)")
                        succes = True
                        break
            except Exception as e:
                print(f"Attente Wyoming {station} ({dt.strftime('%d/%m %HZ')}, essai {essai+1}/3) : {e}")
                if "503" in str(e) or "403" in str(e):
                    time.sleep(15.0)
                    continue
                break

        if succes:
            break

    if not succes:
        print(f"Conservation des données précédentes pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
