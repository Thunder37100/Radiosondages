// --- 1. FORMULES THERMODYNAMIQUES ---
function pressionVapeurSat(tempC) {
  return 6.112 * Math.exp((17.67 * tempC) / (tempC + 243.5));
}

function rapportMelange(tdC, presHpa) {
  if (isNaN(tdC)) return 0;
  const e = pressionVapeurSat(tdC);
  return 0.622 * (e / Math.max(1, presHpa - e));
}

function tempVirtuelle(tempC, tdC, presHpa) {
  const w = rapportMelange(tdC, presHpa);
  return ((tempC + 273.15) * (1 + 0.61 * w)) - 273.15;
}

function tempThermometreMouille(tempC, tdC, presHpa) {
  if (isNaN(tdC)) return tempC;
  const eActuel = pressionVapeurSat(tdC);
  let bas = tdC;
  let haut = tempC;
  const gammaPsy = 0.000662 * presHpa; // Constante psychrométrique (hPa/°C)

  // Recherche par dichotomie (15 itérations = précision < 0.001 °C)
  for (let i = 0; i < 15; i++) {
    const milieu = (bas + haut) / 2;
    const fMilieu = pressionVapeurSat(milieu) - gammaPsy * (tempC - milieu) - eActuel;
    if (fMilieu > 0) {
      haut = milieu;
    } else {
      bas = milieu;
    }
  }
  return (bas + haut) / 2;
}

function gradientAdiabatiqueSature(tempC, presHpa) {
  const Tk = tempC + 273.15;
  const rs = rapportMelange(tempC, presHpa);
  const Lv = 2.501e6, Rd = 287.05, Rv = 461.5, cpd = 1005.0;
  const num = 1 + (Lv * rs) / (Rd * Tk);
  const den = 1 + (Lv * Lv * rs) / (cpd * Rv * Tk * Tk);
  return (9.81 / cpd) * (num / den);
}

// --- 2. ASCENDANCE D'UNE PARTICULE (CAPE / CIN VIRTUELLE) ---
function souleverParticule(niveaux, idxDepart, tInit, tdInit) {
  const nDepart = niveaux.at(idxDepart);
  const hLCL = Math.max(0, 125 * (tInit - tdInit));
  const altLCL = nDepart.alt + hLCL;
  const wInit = rapportMelange(tdInit, nDepart.pres);

    let cape = 0, cin = 0, cinTemp = 0, tParc = tInit;
  const tvInit = tempVirtuelle(tInit, tdInit, nDepart.pres);
  let traceParticule = Array.of({ pres: nDepart.pres, tv: tvInit });

  for (let i = idxDepart; i < niveaux.length - 1; i++) {
    const n1 = niveaux.at(i);
    const n2 = niveaux.at(i + 1);
    if (n2.pres < 100) break;

    const dz = n2.alt - n1.alt;
    const zMoy = (n1.alt + n2.alt) / 2;
    const pMoy = (n1.pres + n2.pres) / 2;

    const estSature = (zMoy >= altLCL);
    const gamma = estSature ? gradientAdiabatiqueSature(tParc, pMoy) : 0.00981;
    tParc -= gamma * dz;

    const wParc = estSature ? rapportMelange(tParc, pMoy) : wInit;
    const tvParc = ((tParc + 273.15) * (1 + 0.61 * wParc)) - 273.15;
    traceParticule.push({ pres: n2.pres, tv: tvParc });

    const tvEnvMoy = (n1.tv + n2.tv) / 2;
    const flott = 9.81 * ((tvParc - tvEnvMoy) / (tvEnvMoy + 273.15)) * dz;

    if (flott > 0) {
      cape += flott;
      cin += cinTemp;
      cinTemp = 0;
    } else if (n2.pres > 400) {
      cinTemp += flott;
    }
  }

  if (cape < 5) { cape = 0; cin = 0; }
  return { cape, cin, hLCL, trace: traceParticule };
}

// --- 3. CALCUL DE TOUS LES INDICES DU TABLEAU ---
function calculerIndices(niveaux) {
  const sol = niveaux.at(0);
  const altSol = sol.alt;

  // SB (Surface)
  const tdSol = isNaN(sol.dwpt) ? sol.temp : sol.dwpt;
  const resSB = souleverParticule(niveaux, 0, sol.temp, tdSol);
  document.getElementById("val-sbcape").innerText = `${Math.round(resSB.cape)} J/kg`;
  document.getElementById("val-sbcin").innerText = `${Math.round(resSB.cin)} J/kg`;
  document.getElementById("val-lcl").innerText = `${Math.round(resSB.hLCL)} m AGL`;

  // ML (Mixed Layer 100 hPa)
  let sumT = 0, sumTd = 0, nbML = 0;
  for (let n of niveaux) {
    if (sol.pres - n.pres <= 100) {
      sumT += n.temp;
      sumTd += isNaN(n.dwpt) ? n.temp : n.dwpt;
      nbML++;
    }
  }
  const resML = (nbML > 0) ? souleverParticule(niveaux, 0, sumT / nbML, sumTd / nbML) : { cape: 0, cin: 0 };
  document.getElementById("val-mlcape").innerText = `${Math.round(resML.cape)} J/kg`;
  document.getElementById("val-mlcin").innerText = `${Math.round(resML.cin)} J/kg`;

  // MU (Most Unstable 300 hPa)
  let meilleurMU = { cape: -1, cin: 0, trace: Array.of() };
  for (let i = 0; i < niveaux.length; i++) {
    const n = niveaux.at(i);
    if (sol.pres - n.pres > 300) break;
    const essai = souleverParticule(niveaux, i, n.temp, isNaN(n.dwpt) ? n.temp : n.dwpt);
    if (essai.cape > meilleurMU.cape) meilleurMU = essai;
  }
  document.getElementById("val-mucape").innerText = `${Math.round(meilleurMU.cape)} J/kg`;
  document.getElementById("val-mucin").innerText = `${Math.round(meilleurMU.cin)} J/kg`;

    // Cinématique (Cisaillement & SRH Bunkers)
  const niveauxVent = niveaux.filter(n => !isNaN(n.u) && !isNaN(n.v) && !isNaN(n.alt));

  function interpAltAGL(cibleAGL) {
    if (niveauxVent.length < 2) return null;
    const cibleAlt = altSol + cibleAGL;
    if (cibleAlt <= niveauxVent.at(0).alt) return { u: niveauxVent.at(0).u, v: niveauxVent.at(0).v };
    if (cibleAlt >= niveauxVent.at(-1).alt) return { u: niveauxVent.at(-1).u, v: niveauxVent.at(-1).v };
    for (let i = 0; i < niveauxVent.length - 1; i++) {
      const n1 = niveauxVent.at(i), n2 = niveauxVent.at(i + 1);
      if (n1.alt <= cibleAlt && n2.alt >= cibleAlt) {
        const f = (n2.alt === n1.alt) ? 0 : (cibleAlt - n1.alt) / (n2.alt - n1.alt);
        return { u: n1.u + f * (n2.u - n1.u), v: n1.v + f * (n2.v - n1.v) };
      }
    }
    return null;
  }

  const v0 = interpAltAGL(0), v1 = interpAltAGL(1000), v6 = interpAltAGL(6000);
  let sh1 = 0, sh6 = 0;

  if (v0 && v1) {
    sh1 = Math.hypot(v1.u - v0.u, v1.v - v0.v);
    document.getElementById("val-shear1").innerText = `${sh1.toFixed(1)} m/s (${(sh1 * 1.94384).toFixed(0)} kt)`;
  }
  if (v0 && v6) {
    sh6 = Math.hypot(v6.u - v0.u, v6.v - v0.v);
    document.getElementById("val-shear6").innerText = `${sh6.toFixed(1)} m/s (${(sh6 * 1.94384).toFixed(0)} kt)`;
  }

  let sumU = 0, sumV = 0, count = 0;
  let vecteurRM = null;
  let srh1 = 0, srh3 = 0;

  for (let z = 0; z <= 6000; z += 500) {
    const vz = interpAltAGL(z);
    if (vz) { sumU += vz.u; sumV += vz.v; count++; }
  }
  if (count > 0 && v0 && v6) {
    const meanU = sumU / count, meanV = sumV / count;
    const dU = v6.u - v0.u, dV = v6.v - v0.v;
    const mag = Math.hypot(dU, dV) || 1;
    const cx = meanU + 7.5 * (dV / mag), cy = meanV - 7.5 * (dU / mag);
    vecteurRM = { u: cx, v: cy };

    for (let i = 0; i < niveauxVent.length - 1; i++) {
      const n1 = niveauxVent.at(i), n2 = niveauxVent.at(i + 1);
      const agl2 = n2.alt - altSol;
      if (agl2 <= 3000) {
        const hel = (n2.u - cx) * (n1.v - cy) - (n1.u - cx) * (n2.v - cy);
        if (agl2 <= 1000) srh1 += hel;
        srh3 += hel;
      }
    }
    document.getElementById("val-srh1").innerText = `${Math.round(srh1)} m²/s²`;
    document.getElementById("val-srh3").innerText = `${Math.round(srh3)} m²/s²`;
  }

  // Gradient 700-500 hPa
  let n700 = null, n500 = null;
  for (let n of niveaux) {
    if (Math.abs(n.pres - 700) < 15) n700 = n;
    if (Math.abs(n.pres - 500) < 15) n500 = n;
  }
  if (n700 && n500) {
    const lapse = (n700.temp - n500.temp) / ((n500.alt - n700.alt) / 1000);
    document.getElementById("val-lapse").innerText = `${lapse.toFixed(1)} °C/km`;
  }

  // --- INDICES COMPOSITES SCP & STP (Formules NOAA / SPC) ---
  // 1. SCP (Supercell Composite Parameter)
  let termeShearSCP = 0;
  if (sh6 >= 10) {
    termeShearSCP = Math.min(sh6 / 20, 1.5);
  }
  let termeCinSCP = 1;
  if (meilleurMU.cin < -40) {
    termeCinSCP = -40 / meilleurMU.cin;
  }
  const scp = Math.max(0, (meilleurMU.cape / 1000) * (srh3 / 50) * termeShearSCP * termeCinSCP);
  document.getElementById("val-scp").innerText = scp.toFixed(1);

  // 2. STP (Significant Tornado Parameter - couches fixes)
  let termeLCL = 1;
  if (resSB.hLCL > 2000) termeLCL = 0;
  else if (resSB.hLCL > 1000) termeLCL = (2000 - resSB.hLCL) / 1000;

  let termeShearSTP = 0;
  if (sh6 >= 12.5) {
    termeShearSTP = Math.min(sh6 / 20, 1.5);
  }

  let termeCinSTP = 1;
  if (resSB.cin < -200) termeCinSTP = 0;
  else if (resSB.cin < -50) termeCinSTP = (200 + resSB.cin) / 150;

  const stp = Math.max(0, (resSB.cape / 1500) * termeLCL * (srh1 / 150) * termeShearSTP * termeCinSTP);
  document.getElementById("val-stp").innerText = stp.toFixed(1);

  return { mu: meilleurMU, rm: vecteurRM };
}
