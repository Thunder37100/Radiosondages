import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = ["07145", "07110", "07510", "07645", "07761"]
os.makedirs("donnees", exist_ok=True)
infos = {}

# On cherche les 3 derniers créneaux synoptiques (00Z / 12Z)
maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = [heure_synoptique - timedelta(hours=12 * i) for i in range(3)]

for station in STATIONS:
    succes = False
    for dt in creneaux:
        date_url = dt.strftime("%Y-%m-%d%%20%H:00:00")
        url = f"https://weather.uwyo.edu/wsgi/sounding?datetime={date_url}&id={station}&type=TEXT:CSV&src=BUFR"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=20) as rep:
                texte = rep.read().decode("utf-8").strip()
                # Vérifie que le CSV contient bien des données (> 10 lignes)
                if "pressure_hPa" in texte and len(texte.splitlines()) > 10:
                    with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                        f.write(texte)
                    infos[station] = dt.strftime("Run du %d/%m/%Y à %HZ")
                    print(f"OK : {station} -> {infos[station]}")
                    succes = True
                    break
        except Exception as e:
            print(f"Attente pour {station} ({dt}) : {e}")
    if not succes:
        print(f"Aucune donnée récente trouvée pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
