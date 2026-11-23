(function () {
  "use strict";
  const DATA = window.RATINGS;
  if (!DATA) {
    document.querySelector(".layout").innerHTML =
      "<p style='padding:20px'>No hay datos. Ejecuta <code>python scoring/engine.py</code>.</p>";
    return;
  }
  const CFG = DATA.config;
  const ROLES = Object.keys(CFG.roles);
  const hasData = (r) => DATA.politicos.some((p) => p.rol === r);
  const SEASONS = [...new Set(DATA.politicos.map((p) => p.temporada))].sort((a, b) => b - a);
  // default season: the one with most rated records (ties -> most recent)
  const ratedIn = (s) => DATA.politicos.filter((p) => p.temporada === s && p.rating != null).length;
  const defSeason = SEASONS.slice().sort((a, b) => ratedIn(b) - ratedIn(a) || b - a)[0];
  const state = { role: ROLES[0], season: defSeason, view: "resumen", sort: "rating", asc: false, q: "", liga: "", partido: "", sel: null, onlyRated: false };

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  function tier(r) {
    if (r == null) return "r-na";
    if (r >= 8) return "r-elite";
    if (r >= 7) return "r-great";
    if (r >= 6.5) return "r-good";
    if (r >= 6) return "r-avg";
    if (r >= 5) return "r-poor";
    return "r-bad";
  }
  const badge = (r, extra = "") => `<span class="rating ${tier(r)} ${extra}">${r == null ? "N/D" : r.toFixed(2)}</span>`;
  const cardsHtml = (p) =>
    p.tarjetas.map((t) => (t.tipo === "amarilla" ? '<span class="card y" title="Amarilla"></span>' : t.tipo === "roja" ? '<span class="card r" title="Roja"></span>' : '<span class="var" title="Proceso abierto">VAR</span>')).join("");

  function fmt(v, unit) {
    if (v == null) return '<span class="na">–</span>';
    if (unit === "bool") return v ? "Sí" : "No";
    if (unit === "%") return Number(v).toFixed(1) + "%";
    if (typeof v === "number" && !Number.isInteger(v)) return v.toFixed(1);
    return esc(v);
  }

  // ---------- header / tabs ----------
  $("#season").innerHTML = SEASONS.map((y) => `<option value="${y}" ${y === state.season ? "selected" : ""}>${y}</option>`).join("");
  $("#season").addEventListener("change", (e) => { state.season = +e.target.value; state.sel = null; render(); renderProfile(); });
  $("#only-rated").addEventListener("change", (e) => { state.onlyRated = e.target.checked; renderTable(); });
  if (DATA.meta?.demo || DATA.meta?.aviso) {
    const b = $("#demo-banner");
    b.hidden = false;
    b.textContent = (DATA.meta.demo ? "⚠ " : "ℹ ") + (DATA.meta.aviso || "Datos de demostración.");
  }

  $("#role-tabs").innerHTML = ROLES.map((r) => `<button role="tab" data-role="${r}">${esc(CFG.roles[r].label)}${hasData(r) ? "" : ' <small style="opacity:.6">(sin datos)</small>'}</button>`).join("");
  $("#role-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    Object.assign(state, { role: b.dataset.role, view: "resumen", sort: "rating", asc: false, liga: "", partido: "" });
    render();
  });

  $("#q").addEventListener("input", (e) => { state.q = e.target.value.toLowerCase(); renderTable(); });
  $("#liga").addEventListener("change", (e) => { state.liga = e.target.value; renderTable(); renderTop(); });
  $("#partido").addEventListener("change", (e) => { state.partido = e.target.value; renderTable(); });

  function rolePols() { return DATA.politicos.filter((p) => p.rol === state.role && p.temporada === state.season); }
  const subtitle = (p) => [p.entidad, p.departamento !== p.entidad ? p.departamento : null, p.partido && p.partido !== "—" ? p.partido : null].filter(Boolean).map(esc).join(" · ");

  function columns() {
    const role = CFG.roles[state.role];
    const cols = [];
    if (state.view === "resumen") {
      cols.push({ key: "liga", label: "Liga", get: (p) => p.liga, l: true });
      for (const [ck, c] of Object.entries(role.categories)) {
        cols.push({ key: "cat:" + ck, label: c.label, get: (p) => p.categorias[ck].rating, html: (p) => { const r = p.categorias[ck].rating; return r == null ? '<span class="na">–</span>' : r.toFixed(2); } });
      }
      cols.push({ key: "cobertura", label: "Cobertura", get: (p) => p.cobertura, html: (p) => Math.round(p.cobertura * 100) + "%" });
    } else if (state.view === "disciplina") {
      const n = (p, t) => p.tarjetas.filter((x) => x.tipo === t).length;
      cols.push({ key: "am", label: "Amarillas", get: (p) => n(p, "amarilla") });
      cols.push({ key: "ro", label: "Rojas", get: (p) => n(p, "roja") });
      cols.push({ key: "var", label: "En investigación", get: (p) => n(p, "investigacion") });
      cols.push({ key: "pen", label: "Penalización", get: (p) => p.penalizacion, html: (p) => (p.penalizacion ? "−" + p.penalizacion.toFixed(2) : "0") });
      cols.push({ key: "raw", label: "Rating sin tarjetas", get: (p) => p.rating_sin_tarjetas, html: (p) => (p.rating_sin_tarjetas == null ? "–" : p.rating_sin_tarjetas.toFixed(2)) });
    } else {
      for (const [mk, m] of Object.entries(role.metrics)) {
        if (m.category !== state.view) continue;
        cols.push({
          key: "m:" + mk, label: m.label, title: m.source + (m.direction < 0 ? " · menor es mejor" : ""),
          get: (p) => { const v = p.metricas[mk].valor; return typeof v === "boolean" ? +v : v; },
          html: (p) => fmt(p.metricas[mk].valor, m.unit),
        });
      }
    }
    return cols;
  }

  function render() {
    document.querySelectorAll("#role-tabs button").forEach((b) => b.setAttribute("aria-selected", b.dataset.role === state.role));
    const role = CFG.roles[state.role];
    const views = [["resumen", "Resumen"], ...Object.entries(role.categories).map(([k, c]) => [k, c.label]), ["disciplina", "Disciplina"]];
    $("#cat-tabs").innerHTML = views.map(([k, l]) => `<button data-v="${k}" class="${k === state.view ? "on" : ""}">${esc(l)}</button>`).join("");
    $("#cat-tabs").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.view = b.dataset.v; render(); } };

    const pols = rolePols();
    const ligas = [...new Set(pols.map((p) => p.liga))].sort();
    $("#liga").innerHTML = `<option value="">Todas las ligas</option>` + ligas.map((l) => `<option ${l === state.liga ? "selected" : ""}>${esc(l)}</option>`).join("");
    $("#liga").hidden = ligas.length < 2;
    const partidos = [...new Set(pols.map((p) => p.partido))].filter((x) => x && x !== "—").sort();
    $("#partido").hidden = partidos.length === 0;
    $("#partido").innerHTML = `<option value="">Todos los partidos</option>` + partidos.map((l) => `<option ${l === state.partido ? "selected" : ""}>${esc(l)}</option>`).join("");
    renderTable();
    renderTop();
  }

  function renderTable() {
    const cols = columns();
    const all = [
      { key: "num", label: "#", cls: "num" },
      { key: "nombre", label: "Nombre", l: true, get: (p) => p.nombre },
      ...cols,
      { key: "tarjetas", label: "", get: (p) => p.penalizacion },
      { key: "rating", label: "Rating", get: (p) => p.rating },
    ];
    $("#grid thead").innerHTML = "<tr>" + all.map((c) =>
      `<th data-k="${c.key}" class="${c.l ? "l" : ""} ${state.sort === c.key ? "sorted" + (state.asc ? " asc" : "") : ""}" title="${esc(c.title || "")}">${esc(c.label)}</th>`).join("") + "</tr>";
    $("#grid thead").onclick = (e) => {
      const th = e.target.closest("th");
      if (!th || th.dataset.k === "num") return;
      if (state.sort === th.dataset.k) state.asc = !state.asc; else { state.sort = th.dataset.k; state.asc = th.dataset.k === "nombre"; }
      renderTable();
    };

    const getter = all.find((c) => c.key === state.sort)?.get || ((p) => p.rating);
    let rows = rolePols().filter((p) =>
      (!state.onlyRated || p.rating != null) &&
      (!state.liga || p.liga === state.liga) &&
      (!state.partido || p.partido === state.partido) &&
      (!state.q || [p.nombre, p.entidad, p.partido, p.departamento].join(" ").toLowerCase().includes(state.q)));
    rows.sort((a, b) => {
      const x = getter(a), y = getter(b);
      if (x == null && y == null) return 0;
      if (x == null) return 1;
      if (y == null) return -1;
      const c = typeof x === "string" ? x.localeCompare(y) : x - y;
      return state.asc ? c : -c;
    });

    if (!hasData(state.role)) {
      $("#grid tbody").innerHTML = `<tr><td colspan="${all.length}" class="l na" style="padding:24px">
        Aún no hay datos de ${esc(CFG.roles[state.role].label.toLowerCase())} en este conjunto. Los conectores del Congreso
        (Senado y Cámara) están en desarrollo; los datos de demo (<code>python scoring/generate_sample.py && python scoring/engine.py</code>) sí los incluyen.</td></tr>`;
      return;
    }
    $("#grid tbody").innerHTML = rows.map((p, i) => `
      <tr data-id="${esc(p.id)}" class="${p.id === state.sel ? "sel" : ""}">
        <td class="num">${i + 1}</td>
        <td class="l who"><strong>${esc(p.nombre)}</strong><span>${subtitle(p)}</span></td>
        ${cols.map((c) => `<td class="${c.l ? "l" : ""}">${c.html ? c.html(p) : esc(c.get(p))}</td>`).join("")}
        <td>${cardsHtml(p)}</td>
        <td>${badge(p.rating)}</td>
      </tr>`).join("") || `<tr><td colspan="${all.length}" class="l na">Sin resultados.</td></tr>`;
    $("#grid tbody").onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) { state.sel = tr.dataset.id; renderTable(); renderProfile(); } };
  }

  function renderTop() {
    const top = rolePols().filter((p) => p.rating != null && (!state.liga || p.liga === state.liga))
      .sort((a, b) => b.rating - a.rating).slice(0, 5);
    $("#top5").innerHTML = top.map((p) => `<li><span>${esc(p.nombre)}</span>${badge(p.rating)}</li>`).join("");
  }

  function renderProfile() {
    const p = DATA.politicos.find((x) => x.id === state.sel);
    const el = $("#profile");
    if (!p) { el.className = "profile empty"; el.textContent = "Selecciona un político para ver su perfil."; return; }
    const role = CFG.roles[p.rol];
    const catBars = Object.entries(role.categories).map(([k, c]) => {
      const r = p.categorias[k].rating;
      const pct = r == null ? 0 : (r / 10) * 100;
      return `<div class="bar"><div class="lbl"><span>${esc(c.label)}</span><span class="src">${Math.round(c.weight * 100)}%</span></div>
        <div class="v">${r == null ? "–" : r.toFixed(2)}</div><div class="track"><div class="fill ${tier(r)}" style="width:${pct}%"></div></div></div>`;
    }).join("");
    const mBars = Object.entries(role.metrics).map(([k, m]) => {
      const e = p.metricas[k];
      const pc = e.percentil;
      const cls = pc == null ? "r-na" : pc >= 80 ? "r-great" : pc >= 60 ? "r-good" : pc >= 40 ? "r-avg" : pc >= 20 ? "r-poor" : "r-bad";
      const src = (p.fuentes && p.fuentes[k]) || m.source;
      return `<div class="bar" title="${esc(src)}"><div class="lbl"><span>${esc(m.label)}</span><span class="src">${fmt(e.valor, m.unit)}</span></div>
        <div class="v">${pc == null ? "–" : "P" + Math.round(pc)}</div><div class="track"><div class="fill ${cls}" style="width:${pc ?? 0}%"></div></div></div>`;
    }).join("");
    const lab = (k) => esc(role.metrics[k].label);
    el.className = "profile";
    el.innerHTML = `
      <div class="ph"><div><h2>${esc(p.nombre)}</h2><p>${esc(role.position)} · ${subtitle(p)}${p.periodo ? " · mandato " + esc(p.periodo) : ""}</p></div>${badge(p.rating, "big")}</div>
      ${p.titular_identificado === false ? `<div class="note">Titular aún no vinculado: se califica el cargo en la temporada ${p.temporada}.</div>` : ""}
      ${p.rating == null ? `<div class="note">Sin rating global: cobertura de datos ${Math.round(p.cobertura * 100)}% &lt; ${Math.round(CFG.rating.min_coverage * 100)}% mínimo (como no tener minutos suficientes). Las categorías con datos sí se muestran.</div>` : ""}
      <div class="meta">
        <div>Partido: <b>${esc(p.partido)}</b></div><div>Liga: <b>${esc(p.liga)}</b></div>
        <div>Puesto en rol: <b>${p.rank_rol ?? "–"}</b></div><div>Puesto en liga: <b>${p.rank_liga ?? "–"}</b></div>
        <div>Pares comparados: <b>${p.grupo_pares}</b></div><div>Cobertura de datos: <b>${Math.round(p.cobertura * 100)}%</b></div>
      </div>
      <h4>Categorías</h4>${catBars}
      ${p.fortalezas.length ? `<h4>Fortalezas</h4><div class="tags">${p.fortalezas.map((k) => `<span class="tag s">${lab(k)}</span>`).join("")}</div>` : ""}
      ${p.debilidades.length ? `<h4>Debilidades</h4><div class="tags">${p.debilidades.map((k) => `<span class="tag w">${lab(k)}</span>`).join("")}</div>` : ""}
      <h4>Disciplina</h4>
      ${p.tarjetas.length ? `<ul class="cards-list">${p.tarjetas.map((t) => `<li>${cardsHtml({ tarjetas: [t] })} ${esc(t.descripcion)} <span class="src">— ${esc(t.fuente)}</span></li>`).join("")}</ul>` : '<p class="src">Sin tarjetas.</p>'}
      <h4>Estadísticas (percentil vs. pares)</h4>${mBars}
      ${p.secop ? `<p class="src">SECOP ${p.temporada}: ${p.secop.contratos.toLocaleString("es-CO")} contratos${p.secop.contratos_secop1 ? ` (${p.secop.contratos_secop1.toLocaleString("es-CO")} en SECOP I)` : ""}, ${p.secop.procesos_competitivos} procesos competitivos.</p>` : ""}`;
  }

  render();
})();
