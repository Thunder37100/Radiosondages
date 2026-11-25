import os
import re
import json
import time
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = ("07145", "07110", "07510", "07645", "07761")
os.makedirs("donnees", exist_ok=True)
infos = {}

maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = [heure_synoptique - timedelta(hours=12 * i) for i in range(4)]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
    "Referer": "https://uwyo.edu"
}

for station in STATIONS:
    succes = False
    for dt in creneaux:
        annee = dt.strftime("%Y")
        mois = dt.strftime("%m")
        jour_heure = dt.strftime("%d%H")
        url = (
            "https://uwyo.edu"
            f"?region=europe&TYPE=TEXT%3ALIST&YEAR={annee}&MONTH={mois}&FROM={jour_heure}&TO={jour_heure}&STNM={station}"
        )
        try:
            time.sleep(2.5)  # Pause de courtoisie pour éviter l'erreur 503 Too Busy
            req = urllib.request.Request(url, headers=HEADERS)
            with urllib.request.urlopen(req, timeout=25) as rep:
                html = rep.read().decode("utf-8", errors="ignore")
                bloc_pre = re.search(r"<PRE>(.*?)</PRE>", html, re.DOTALL | re.IGNORECASE)
                if bloc_pre:
                    lignes_brutes = bloc_pre.group(1).splitlines()
                    lignes_csv = [
                        "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                    ]
                    for ligne in lignes_brutes:
                        morceaux = ligne.split()
                        # Une ligne de mesure valide commence par une pression numérique et contient au moins 8 colonnes
                        if len(morceaux) >= 8:
                            try:
                                p = float(morceaux.pop(0))
                                h = float(morceaux.pop(0))
                                t = float(morceaux.pop(0))
                                td = float(morceaux.pop(0))
                                _rh = morceaux.pop(0)
                                _mixr = morceaux.pop(0)
                                dr = float(morceaux.pop(0))
                                sknt = float(morceaux.pop(0))
                                vit_ms = sknt * 0.514444
                                lignes_csv.append(f"{p},{h},{t},{td},{dr:.0f},{vit_ms:.1f}")
                            except ValueError:
                                continue

                    if len(lignes_csv) > 15:
                        with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                            f.write("\n".join(lignes_csv))
                        infos[station] = dt.strftime("Run du %d/%m/%Y à %HZ")
                        print(f"OK : {station} -> {infos[station]} ({len(lignes_csv)-1} niveaux)")
                        succes = True
                        break
        except Exception as e:
            print(f"Attente pour {station} ({dt.strftime('%Y-%m-%d %HZ')}) : {e}")
    if not succes:
        print(f"Aucune donnée récente trouvée pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
