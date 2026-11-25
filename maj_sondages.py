import os
import json
import urllib.request
from datetime import datetime, timedelta, timezone

STATIONS = ["07145", "07110", "07510", "07645", "07761"]
os.makedirs("donnees", exist_ok=True)
infos = {}

# Construction propre de l'adresse de base de l'API Iowa State (IEM)
DOMAINE = "mesonet.agron.iastate.edu"
CHEMIN = "/json/raob.py"

maintenant = datetime.now(timezone.utc)
heure_synoptique = maintenant.replace(hour=(maintenant.hour // 12) * 12, minute=0, second=0, microsecond=0)
creneaux = [heure_synoptique - timedelta(hours=12 * i) for i in range(4)]

for station in STATIONS:
    succes = False
    for dt in creneaux:
        ts_iso = dt.strftime("%Y-%m-%dT%H:%M:%SZ")
        url = "https://" + DOMAINE + CHEMIN + f"?ts={ts_iso}&station={station}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MeteoAssoBot/1.0"})
            with urllib.request.urlopen(req, timeout=20) as rep:
                data = json.loads(rep.read().decode("utf-8"))
                profiles = data.get("profiles", [])
                if profiles and len(profiles.get("profile", [])) > 10:
                    lignes_csv = [
                        "pressure_hPa,geopotential height_m,temperature_C,dew point temperature_C,wind direction_degree,wind speed_m/s"
                    ]
                    for pt in profiles["profile"]:
                        p = pt.get("pres")
                        h = pt.get("hght")
                        t = pt.get("tmpc")
                        td = pt.get("dwpc")
                        dr = pt.get("drct")
                        sknt = pt.get("sknt")

                        if p is not None and h is not None and t is not None:
                            td_str = f"{td:.1f}" if td is not None else "NaN"
                            dr_str = f"{dr:.0f}" if dr is not None else "NaN"
                            vit_str = f"{(sknt * 0.514444):.1f}" if sknt is not None else "NaN"
                            lignes_csv.append(f"{p},{h},{t},{td_str},{dr_str},{vit_str}")

                    if len(lignes_csv) > 10:
                        with open(f"donnees/{station}.csv", "w", encoding="utf-8") as f:
                            f.write("\n".join(lignes_csv))
                        infos[station] = dt.strftime("Run du %d/%m/%Y à %HZ")
                        print(f"OK : {station} -> {infos[station]} ({len(lignes_csv)-1} niveaux)")
                        succes = True
                        break
        except Exception as e:
            print(f"Attente pour {station} ({ts_iso}) : {e}")
    if not succes:
        print(f"Aucune donnée récente trouvée pour {station}")

with open("donnees/infos.json", "w", encoding="utf-8") as f:
    json.dump(infos, f, ensure_ascii=False, indent=2)
