const inputFichier = document.getElementById("fichier-csv");
const selectStation = document.getElementById("select-station");
const infoFichier = document.getElementById("info-fichier");

const STATIONS_OMM = {
  "07145": "Trappes (France)",
  "07110": "Brest-Guipavas (France)",
  "07510": "Bordeaux-Mérignac (France)",
  "07645": "Nîmes-Courbessac (France)",
  "07761": "Ajaccio (France)",
  "07481": "Lyon-Satolas (France)"
};

// Fonction pour charger automatiquement un sondage hébergé dans /donnees/
async function chargerStationEnLigne(codeStation) {
  const nomLieu = STATIONS_OMM[codeStation] || codeStation;
  infoFichier.innerText = `Chargement de ${nomLieu}...`;

  try {
    // 1. On lit le fichier infos.json généré par le robot pour connaître l'heure du run
    let texteRun = "Dernier run disponible";
    const repInfos = await fetch("donnees/infos.json?t=" + Date.now());
    if (repInfos.ok) {
      const infos = await repInfos.json();
      if (infos[codeStation]) texteRun = infos[codeStation];
    }

    // 2. On télécharge le CSV de la station
    const repCSV = await fetch(`donnees/${codeStation}.csv?t=` + Date.now());
    if (!repCSV.ok) throw new Error("Fichier non disponible");

    const contenuCSV = await repCSV.text();
    infoFichier.innerText = `${nomLieu} — ${texteRun}`;
    traiterCSV(contenuCSV);
  } catch (err) {
    infoFichier.innerText = `${nomLieu} : en attente de la première mise à jour automatique (ou chargez un CSV manuel).`;
  }
}

// Quand l'utilisateur change de station dans le menu déroulant
selectStation.addEventListener("change", function() {
  chargerStationEnLigne(selectStation.value);
});

// Au démarrage de la page, on charge Trappes automatiquement !
window.addEventListener("DOMContentLoaded", function() {
  chargerStationEnLigne(selectStation.value);
});

// Import manuel d'un fichier CSV local (conservé pour les archives)
function decoderNomFichier(nomFichier) {
  const sansExtension = nomFichier.replace(".csv", "").replace(".txt", "");
  const morceaux = sansExtension.split("-");
  if (morceaux.length === 2 && morceaux.at(0).length === 10) {
    const d = morceaux.at(0), code = morceaux.at(1);
    const nomLieu = STATIONS_OMM[code] || `Station OMM ${code}`;
    return `${nomLieu} — Run du ${d.slice(6, 8)}/${d.slice(4, 6)}/${d.slice(0, 4)} à ${d.slice(8, 10)}Z`;
  }
  return "Fichier : " + nomFichier;
}

inputFichier.addEventListener("change", function(evenement) {
  const fichier = evenement.target.files.item(0);
  if (!fichier) return;
  infoFichier.innerText = decoderNomFichier(fichier.name);
  const lecteur = new FileReader();
  lecteur.onload = function(e) { traiterCSV(e.target.result); };
  lecteur.readAsText(fichier);
});

function traiterCSV(texte) {
  const lignes = texte.trim().split("\n");
  const colonnesBrutes = lignes.at(0).split(",");
  let nomsColonnes = Array.of();
  for (let i = 0; i < colonnesBrutes.length; i++) nomsColonnes.push(colonnesBrutes.at(i).trim());

  const idxPres = nomsColonnes.indexOf("pressure_hPa");
  const idxAlt  = nomsColonnes.indexOf("geopotential height_m");
  const idxTemp = nomsColonnes.indexOf("temperature_C");
  const idxDwpt = nomsColonnes.indexOf("dew point temperature_C");
  const idxDir  = nomsColonnes.indexOf("wind direction_degree");
  const idxVit  = nomsColonnes.indexOf("wind speed_m/s");

  let niveaux = Array.of();
  for (let i = 1; i < lignes.length; i++) {
    const valeurs = lignes.at(i).split(",");
    if (valeurs.length === nomsColonnes.length) {
      const pres = parseFloat(valeurs.at(idxPres));
      const alt  = parseFloat(valeurs.at(idxAlt));
      const temp = parseFloat(valeurs.at(idxTemp));
      const dwpt = parseFloat(valeurs.at(idxDwpt));
      const dir  = parseFloat(valeurs.at(idxDir));
      const vit  = parseFloat(valeurs.at(idxVit));

      if (!isNaN(pres) && !isNaN(alt) && !isNaN(temp)) {
        const tv = tempVirtuelle(temp, dwpt, pres);
        const tw = tempThermometreMouille(temp, dwpt, pres);
        let u = NaN, v = NaN;
        if (!isNaN(dir) && !isNaN(vit)) {
          const rad = dir * (Math.PI / 180);
          u = -vit * Math.sin(rad);
          v = -vit * Math.cos(rad);
        }
        niveaux.push({ pres, alt, temp, dwpt, tv, tw, dir, vit, u, v });
      }
    }
  }

    if (niveaux.length > 0) {
    const resultats = calculerIndices(niveaux);
    dessinerSkewT(niveaux, resultats.mu);
    dessinerHodographe(niveaux, resultats.rm);
  }
}

function dessinerBarbule(ctx, x, y, dirDeg, vitMs) {
  const noeuds = vitMs * 1.94384;
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate((dirDeg * Math.PI) / 180);
  ctx.strokeStyle = "#1e293b";
  ctx.fillStyle = "#1e293b";
  ctx.lineWidth = 1.3;

  ctx.beginPath(); ctx.arc(0, 0, 2, 0, 2 * Math.PI); ctx.fill();
  if (noeuds < 2.5) {
    ctx.beginPath(); ctx.arc(0, 0, 5, 0, 2 * Math.PI); ctx.stroke();
    ctx.restore(); return;
  }

  const longHampe = 26;
  ctx.beginPath(); ctx.moveTo(0, 0); ctx.lineTo(0, -longHampe); ctx.stroke();

  let reste = Math.round(noeuds / 5) * 5;
  let posY = -longHampe;
  while (reste >= 50) {
    ctx.beginPath(); ctx.moveTo(0, posY); ctx.lineTo(9, posY + 3); ctx.lineTo(0, posY + 6); ctx.closePath(); ctx.fill();
    posY += 8; reste -= 50;
  }
  while (reste >= 10) {
    ctx.beginPath(); ctx.moveTo(0, posY); ctx.lineTo(9, posY - 3); ctx.stroke();
    posY += 4.5; reste -= 10;
  }
  if (reste >= 5) {
    if (posY === -longHampe) posY += 4.5;
    ctx.beginPath(); ctx.moveTo(0, posY); ctx.lineTo(5, posY - 1.5); ctx.stroke();
  }
  ctx.restore();
}

function dessinerSkewT(donnees, resMU) {
  const canvas = document.getElementById("canvas-skewt");
  const ctx = canvas.getContext("2d");
  const L = canvas.width, H = canvas.height;
  const margeG = 42, margeD = 65, margeH = 15, margeB = 30;
  const zoneL = L - margeG - margeD, zoneH = H - margeH - margeB;
  const pMax = 1050, pMin = 100, tMin = -40, tMax = 40;

  function presVersY(p) {
    return (H - margeB) - ((Math.log(pMax) - Math.log(p)) / (Math.log(pMax) - Math.log(pMin))) * zoneH;
  }
  function tempVersX(t, y) {
    return margeG + ((t - tMin) / (tMax - tMin)) * zoneL + ((H - margeB) - y) * 0.85;
  }

  ctx.clearRect(0, 0, L, H);

  const niveauxP = "1000,925,850,700,500,400,300,250,200,150,100".split(",");
  ctx.font = "11px Arial"; ctx.fillStyle = "#475569";
  for (let pTxt of niveauxP) {
    const p = Number(pTxt), y = presVersY(p);
    ctx.strokeStyle = "#e2e8f0"; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(margeG, y); ctx.lineTo(margeG + zoneL, y); ctx.stroke();
    ctx.fillText(p, 5, y + 4);
  }

  ctx.save();
  ctx.beginPath(); ctx.rect(margeG, margeH, zoneL, zoneH); ctx.clip();

  // Adiabatiques sèches
  ctx.strokeStyle = "#fde68a"; ctx.lineWidth = 1;
  for (let thetaC = -30; thetaC <= 130; thetaC += 10) {
    const thetaK = thetaC + 273.15;
    ctx.beginPath();
    let debut = true;
    for (let p = 1050; p >= 100; p -= 25) {
      const tC = thetaK * Math.pow(p / 1000, 0.2857) - 273.15;
      const y = presVersY(p), x = tempVersX(tC, y);
      if (debut) { ctx.moveTo(x, y); debut = false; } else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }

  // Adiabatiques saturées
  ctx.strokeStyle = "#bbf7d0"; ctx.setLineDash(Array.of(4, 3));
  for (let tDepart = -10; tDepart <= 35; tDepart += 5) {
    let tCourant = tDepart;
    ctx.beginPath();
    let debut = true;
    for (let p = 1000; p >= 150; p -= 20) {
      const y = presVersY(p), x = tempVersX(tCourant, y);
      if (debut) { ctx.moveTo(x, y); debut = false; } else ctx.lineTo(x, y);
      const dz = (287.05 * (tCourant + 273.15) / (9.81 * p)) * 20;
      tCourant -= gradientAdiabatiqueSature(tCourant, p) * dz;
    }
    ctx.stroke();
  }
  ctx.setLineDash(Array.of());

  // Isothermes
  for (let t = -80; t <= 50; t += 10) {
    ctx.strokeStyle = (t === 0) ? "#0284c7" : "#e2e8f0";
    ctx.lineWidth = (t === 0) ? 1.5 : 0.9;
    ctx.beginPath(); ctx.moveTo(tempVersX(t, H - margeB), H - margeB); ctx.lineTo(tempVersX(t, margeH), margeH); ctx.stroke();
  }

  // Température virtuelle Tv (pointillé rouge)
  ctx.strokeStyle = "#ef4444"; ctx.lineWidth = 1.3; ctx.setLineDash(Array.of(3, 3));
  ctx.beginPath();
  let debutTv = true;
  for (let d of donnees) {
    if (d.pres >= 100 && !isNaN(d.tv)) {
      const y = presVersY(d.pres), x = tempVersX(d.tv, y);
      if (debutTv) { ctx.moveTo(x, y); debutTv = false; } else ctx.lineTo(x, y);
    }
  }
  ctx.stroke(); ctx.setLineDash(Array.of());

  // Particule MU si CAPE > 0
  if (resMU && resMU.cape > 0 && resMU.trace.length > 0) {
    ctx.strokeStyle = "#0f172a"; ctx.lineWidth = 1.8; ctx.setLineDash(Array.of(5, 4));
    ctx.beginPath();
    let debutP = true;
    for (let pt of resMU.trace) {
      const y = presVersY(pt.pres), x = tempVersX(pt.tv, y);
      if (debutP) { ctx.moveTo(x, y); debutP = false; } else ctx.lineTo(x, y);
    }
    ctx.stroke(); ctx.setLineDash(Array.of());
  }

  // Courbe du Thermomètre Mouillé Tw (bleu cyan)
ctx.strokeStyle = "#06b6d4";
ctx.lineWidth = 1.6;
ctx.beginPath();
let debutTw = true;
for (let d of donnees) {
if (d.pres >= 100 && !isNaN(d.tw)) {
const y = presVersY(d.pres);
const x = tempVersX(d.tw, y);
if (debutTw) { ctx.moveTo(x, y); debutTw = false; }
else ctx.lineTo(x, y);
}
}
ctx.stroke();

  // Courbe T (rouge) & Td (vert)
  ctx.strokeStyle = "#dc2626"; ctx.lineWidth = 2.8; ctx.beginPath();
  let debutT = true;
  for (let d of donnees) {
    if (d.pres >= 100) {
      const y = presVersY(d.pres), x = tempVersX(d.temp, y);
      if (debutT) { ctx.moveTo(x, y); debutT = false; } else ctx.lineTo(x, y);
    }
  }
  ctx.stroke();

  ctx.strokeStyle = "#16a34a"; ctx.lineWidth = 2.5; ctx.beginPath();
  let debutTd = true;
  for (let d of donnees) {
    if (d.pres >= 100 && !isNaN(d.dwpt)) {
      const y = presVersY(d.pres), x = tempVersX(d.dwpt, y);
      if (debutTd) { ctx.moveTo(x, y); debutTd = false; } else ctx.lineTo(x, y);
    }
  }
  ctx.stroke();
  ctx.restore();

  ctx.strokeStyle = "#334155"; ctx.lineWidth = 1.5;
  ctx.strokeRect(margeG, margeH, zoneL, zoneH);
  ctx.fillStyle = "#334155";
  for (let t = -30; t <= 40; t += 10) ctx.fillText(t + "°", tempVersX(t, H - margeB) - 10, H - 10);

  // Barbules de vent
  const xAxeVent = margeG + zoneL + 32;
  ctx.strokeStyle = "#cbd5e1"; ctx.lineWidth = 1;
  ctx.beginPath(); ctx.moveTo(xAxeVent, margeH); ctx.lineTo(xAxeVent, margeH + zoneH); ctx.stroke();

  let dernierY = 9999;
  for (let d of donnees) {
    if (d.pres >= 100 && !isNaN(d.dir) && !isNaN(d.vit)) {
      const y = presVersY(d.pres);
      if (Math.abs(dernierY - y) >= 22) {
        dessinerBarbule(ctx, xAxeVent, y, d.dir, d.vit);
        dernierY = y;
      }
    }
  }
}

function dessinerHodographe(points, vecteurRM) {
  const canvas = document.getElementById("canvas-hodographe");
  const ctx = canvas.getContext("2d");
  const largeur = canvas.width, hauteur = canvas.height;
  const centreX = largeur / 2, centreY = hauteur / 2;
  const echelle = 2.8;

  ctx.clearRect(0, 0, largeur, hauteur);
  ctx.strokeStyle = "#cbd5e1";
  ctx.fillStyle = "#64748b";
  ctx.font = "10px Arial";
  ctx.lineWidth = 1;

  for (let vitesse = 10; vitesse <= 50; vitesse += 10) {
    const rayon = vitesse * echelle;
    ctx.beginPath();
    ctx.arc(centreX, centreY, rayon, 0, 2 * Math.PI);
    ctx.stroke();
    ctx.fillText(vitesse + " m/s", centreX + 3, centreY - rayon + 10);
  }

  ctx.strokeStyle = "#94a3b8";
  ctx.beginPath();
  ctx.moveTo(0, centreY); ctx.lineTo(largeur, centreY);
  ctx.moveTo(centreX, 0); ctx.lineTo(centreX, hauteur);
  ctx.stroke();

  const altSol = points.at(0).alt;
  if (vecteurRM) {
    const rmX = centreX + vecteurRM.u * echelle;
    const rmY = centreY - vecteurRM.v * echelle;
    ctx.fillStyle = "rgba(239, 68, 68, 0.16)";
    ctx.beginPath();
    ctx.moveTo(rmX, rmY);
    for (let i = 0; i < points.length; i++) {
      const p = points.at(i);
      if (p.alt - altSol > 3000) break;
      if (!isNaN(p.u) && !isNaN(p.v)) {
        ctx.lineTo(centreX + p.u * echelle, centreY - p.v * echelle);
      }
    }
    ctx.closePath();
    ctx.fill();
  }

  for (let i = 0; i < points.length - 1; i++) {
    const p1 = points.at(i), p2 = points.at(i + 1);
    if (p2.alt > 12000) break;
    if (isNaN(p1.u) || isNaN(p2.u)) continue;
    const x1 = centreX + p1.u * echelle, y1 = centreY - p1.v * echelle;
    const x2 = centreX + p2.u * echelle, y2 = centreY - p2.v * echelle;

    if (p1.alt - altSol < 3000) ctx.strokeStyle = "#ef4444";
    else if (p1.alt - altSol < 6000) ctx.strokeStyle = "#22c55e";
    else if (p1.alt - altSol < 9000) ctx.strokeStyle = "#3b82f6";
    else ctx.strokeStyle = "#a855f7";

    ctx.lineWidth = 2.8;
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  if (vecteurRM) {
    const rmX = centreX + vecteurRM.u * echelle;
    const rmY = centreY - vecteurRM.v * echelle;
    ctx.strokeStyle = "#0f172a";
    ctx.lineWidth = 1.3;
    ctx.setLineDash(Array.of(4, 3));
    ctx.beginPath();
    ctx.moveTo(centreX, centreY);
    ctx.lineTo(rmX, rmY);
    ctx.stroke();
    ctx.setLineDash(Array.of());

    ctx.fillStyle = "#0f172a";
    ctx.beginPath();
    ctx.arc(rmX, rmY, 4, 0, 2 * Math.PI);
    ctx.fill();
    ctx.font = "bold 11px Arial";
    ctx.fillText("RM", rmX + 6, rmY + 4);
  }
}
