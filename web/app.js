(function () {
  "use strict";
  // Vista interna (archivo local, no publicado) si existe; si no, la pública.
  const DATA = window.RATINGS_INTERNO || window.RATINGS;
  if (!DATA) {
    document.querySelector(".layout").innerHTML =
      "<p style='padding:20px'>No hay datos. Ejecuta <code>python scoring/engine.py</code>.</p>";
    return;
  }
  const CFG = DATA.config;
  // Orden de las pestañas: primero Senado, luego gobernaciones, alcaldías y Cámara.
  const ORDER = ["senador", "gobernador", "alcalde", "representante"];
  const ROLES = Object.keys(CFG.roles).sort((a, b) => (ORDER.indexOf(a) + 99 * (ORDER.indexOf(a) < 0)) - (ORDER.indexOf(b) + 99 * (ORDER.indexOf(b) < 0)));
  const hasData = (r) => DATA.politicos.some((p) => p.rol === r);
  // Sin temporadas: cada registro es la persona en su cargo durante todo su mandato.
  const state = { role: ROLES[0], view: "resumen", sort: "rating", asc: false, q: "", liga: "", partido: "", sel: null, onlyRated: false, layout: "cards" };

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
  // Nombre visible del grupo de comparación ("Única" = todos los del rol)
  const grupo = (l) => (l === "Única" || l === "General" ? "General" : l || "General");

  function fmt(v, unit) {
    if (v == null) return '<span class="na">–</span>';
    if (unit === "bool") return v ? "Sí" : "No";
    if (unit === "%") return Number(v).toFixed(1) + "%";
    if (typeof v === "number" && !Number.isInteger(v)) return v.toFixed(1);
    return esc(v);
  }

  // ---------- header / tabs ----------
  $("#only-rated").addEventListener("change", (e) => { state.onlyRated = e.target.checked; renderTable(); });
  $("#view-toggle").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) { state.layout = b.dataset.l; renderTable(); } });
  if (DATA.meta?.demo || DATA.meta?.aviso) {
    const b = $("#demo-banner");
    b.hidden = false;
    b.textContent = (DATA.meta.demo ? "⚠ " : "ℹ ") + (DATA.meta.aviso || "Datos de demostración.");
  }

  $("#role-tabs").innerHTML = ROLES.map((r) => `<button role="tab" data-role="${r}">${esc(CFG.roles[r].label)}${hasData(r) ? "" : ' <small style="opacity:.6">(sin datos)</small>'}</button>`).join("");
  $("#role-tabs").addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    Object.assign(state, { role: b.dataset.role, view: "resumen", sort: "rating", asc: false, liga: "", partido: "", sel: null });
    render();
  });

  $("#q").addEventListener("input", (e) => { state.q = e.target.value.toLowerCase(); renderTable(); });
  $("#liga").addEventListener("change", (e) => { state.liga = e.target.value; renderTable(); renderTop(); });
  $("#partido").addEventListener("change", (e) => { state.partido = e.target.value; renderTable(); });

  const REPO = "https://github.com/Pidual/Integridad-Politica-Colombiana";
  // Participación ciudadana -------------------------------------------------
  // Comentarios con Giscus (GitHub Discussions). Se activa al completar categoryId:
  // 1) Settings → General → Features → Discussions  2) instalar https://github.com/apps/giscus
  // 3) en https://giscus.app copiar data-category-id de la categoría "Debate" y pegarlo aquí.
  const GISCUS = { repo: "Pidual/Integridad-Politica-Colombiana", repoId: "R_kgDOV5AXcg", category: "Debate", categoryId: "" };
  const aportarHref = (p) => `${REPO}/issues/new?template=aportar-evidencia.yml&title=${encodeURIComponent("Evidencia: " + p.nombre)}&persona=${encodeURIComponent(p.nombre)}&enlace=${encodeURIComponent(location.href)}`;
  const rectHref = (p) => `${REPO}/issues/new?template=rectificacion.yml&title=${encodeURIComponent("Rectificación: " + p.nombre)}&persona=${encodeURIComponent(p.nombre)}&enlace=${encodeURIComponent(location.href)}`;
  // verdict colour for integrity grades: base 8 = neutral
  const verdict = (p) => {
    if (p.rating_principal !== "integridad" || p.rating == null) return "";
    const base = (CFG.integridad && CFG.integridad.base) || 8;
    return p.rating < base - 2 ? "bad" : p.rating < base ? "warn" : p.rating > base ? "good" : "";
  };
  const isInteg = (rol) => (DATA.politicos.find((p) => p.rol === rol) || {}).rating_principal === "integridad";
  const ESTADO_LABEL = { sin_proceso: "Sin proceso", preliminar: "Indagación preliminar", abierto: "Proceso abierto",
    condena_no_firme: "Condena no en firme", en_firme: "En firme", archivado: "Archivado", absuelto: "Absuelto / negado",
    revocado: "Revocado", desmentido: "Desmentido" };

  function rolePols() { return DATA.politicos.filter((p) => p.rol === state.role); }
  const initials = (n) => String(n || "?").replace(/\(.*?\)/g, "").split(/\s+/).filter((w) => w && w[0] === w[0].toUpperCase() && !/^(de|del|la|los)$/i.test(w)).slice(0, 2).map((w) => w[0]).join("");
  const avatar = (p, big = false) => {
    const cls = "av" + (big === "hero" ? " av-hero" : big ? " av-big" : "");
    const fallback = `<span class="${cls} av-ini">${esc(initials(p.nombre))}</span>`;
    if (!p.foto) return fallback;
    // onerror: swap a broken photo for initials
    return `<img class="${cls}" src="${esc(p.foto)}" alt="" loading="lazy" referrerpolicy="no-referrer" onerror="this.outerHTML='${fallback.replace(/"/g, "&quot;").replace(/'/g, "&#39;")}'">`;
  };
  const subtitle = (p) => [p.entidad, p.departamento !== p.entidad ? p.departamento : null, p.partido && p.partido !== "—" ? p.partido : null].filter(Boolean).map(esc).join(" · ");

  function columns() {
    const role = CFG.roles[state.role];
    const cols = [];
    if (state.view === "resumen" && isInteg(state.role)) {
      cols.push({ key: "ev", label: "Eventos", get: (p) => p.integridad.n_eventos, html: (p) => p.integridad.n_eventos ? `<b>${p.integridad.n_eventos}</b>` : '<span class="na">0</span>' });
      cols.push({ key: "resta", label: "En contra", get: (p) => p.integridad.resta_total, html: (p) => p.integridad.resta_total ? `<span class="neg">−${p.integridad.resta_total.toFixed(1)}</span>` : '<span class="na">0</span>' });
      cols.push({ key: "suma", label: "A favor", get: (p) => p.integridad.suma_total, html: (p) => p.integridad.suma_total ? `<span class="pos">+${p.integridad.suma_total.toFixed(2)}</span>` : '<span class="na">0</span>' });
      cols.push({ key: "pend", label: "Sin revisar", get: (p) => p.integridad.pendientes_revision, html: (p) => p.integridad.pendientes_revision ? `<span class="chip warn">${p.integridad.pendientes_revision}</span>` : "" });
      cols.push({ key: "rend", label: "Actividad (info)", title: "Rendimiento legislativo de la legislatura en curso; no cuenta en la nota", get: (p) => p.rating_rendimiento, html: (p) => p.rating_rendimiento == null ? "–" : `<span class="src">${p.rating_rendimiento.toFixed(2)}</span>` });
    } else if (state.view === "resumen") {
      cols.push({ key: "liga", label: "Grupo de comparación", get: (p) => grupo(p.liga), l: true });
      for (const [ck, c] of Object.entries(role.categories)) {
        cols.push({ key: "cat:" + ck, label: c.label, get: (p) => p.categorias[ck].rating, html: (p) => { const r = p.categorias[ck].rating; return r == null ? '<span class="na">–</span>' : r.toFixed(2); } });
      }
      cols.push({ key: "cobertura", label: "Cobertura", get: (p) => p.cobertura, html: (p) => Math.round(p.cobertura * 100) + "%" });
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
    const views = [["resumen", "Resumen"], ...Object.entries(role.categories).map(([k, c]) => [k, c.label])];
    $("#cat-tabs").innerHTML = views.map(([k, l]) => `<button data-v="${k}" class="${k === state.view ? "on" : ""}">${esc(l)}</button>`).join("");
    $("#cat-tabs").onclick = (e) => { const b = e.target.closest("button"); if (b) { state.view = b.dataset.v; render(); } };

    const pols = rolePols();
    const ligas = [...new Set(pols.map((p) => p.liga))].sort();
    $("#liga").innerHTML = `<option value="">Todos los grupos</option>` + ligas.map((l) => `<option value="${esc(l)}" ${l === state.liga ? "selected" : ""}>${esc(grupo(l))}</option>`).join("");
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
      { key: "rating", label: isInteg(state.role) ? "Integridad" : "Rating", get: (p) => p.rating },
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
    const useCards = isInteg(state.role) && state.view === "resumen" && state.layout === "cards";
    $("#view-toggle").hidden = !(isInteg(state.role) && state.view === "resumen");
    $("#view-toggle").querySelectorAll("button").forEach((b) => b.classList.toggle("on", b.dataset.l === state.layout));
    $("#cards").hidden = !useCards;
    $(".table-wrap").hidden = useCards;
    if (useCards) {
      $("#cards").innerHTML = rows.map((p) => {
        const I = p.integridad || {};
        const ev = [I.n_negativos ? `${I.n_negativos} en contra` : "", I.n_positivos ? `${I.n_positivos} a favor` : ""].filter(Boolean).join(" · ") || "Sin hallazgos registrados";
        return `<a class="pcard ${verdict(p)}" href="${personHref(p)}">
          <span class="pcard-rank">#${p.rank_rol ?? "–"}</span>
          <div class="pcard-top">${avatar(p, true)}<div><div class="pcard-name">${esc(p.nombre)}</div>
            <div class="pcard-sub">${esc(p.partido && p.partido !== "—" ? p.partido : "")}${p.periodo ? " · " + esc(p.periodo) : ""}</div></div></div>
          <div class="pcard-score"><div><div class="pcard-k">Integridad</div><div class="pcard-v">${p.rating == null ? "N/D" : p.rating.toFixed(2)}</div></div>
            <div class="pcard-ev">${ev}</div></div>
          <span class="pcard-btn">Ver expediente</span></a>`;
      }).join("") || '<p class="na" style="padding:16px">Sin resultados.</p>';
      return;
    }
    $("#grid tbody").innerHTML = rows.map((p, i) => `
      <tr data-id="${esc(p.id)}" class="${p.id === state.sel ? "sel" : ""}">
        <td class="num">${i + 1}</td>
        <td class="l who"><div class="who-row">${avatar(p)}<div><strong>${esc(p.nombre)}</strong><span>${subtitle(p)}</span></div></div></td>
        ${cols.map((c) => `<td class="${c.l ? "l" : ""}">${c.html ? c.html(p) : esc(c.get(p))}</td>`).join("")}
        <td>${badge(p.rating)}</td>
      </tr>`).join("") || `<tr><td colspan="${all.length}" class="l na">Sin resultados.</td></tr>`;
    $("#grid tbody").onclick = (e) => { const tr = e.target.closest("tr[data-id]"); if (tr) go(tr.dataset.id); };
  }

  function renderTop() {
    const top = rolePols().filter((p) => p.rating != null && (!state.liga || p.liga === state.liga))
      .sort((a, b) => b.rating - a.rating).slice(0, 5);
    $("#top5").innerHTML = top.map((p) => `<li><a class="who-row" href="${personHref(p)}">${avatar(p)}<span>${esc(p.nombre)}</span></a>${badge(p.rating)}</li>`).join("");
  }

  // ================================================================ person page
  const BY_ID = new Map(DATA.politicos.map((p) => [p.id, p]));
  function personHref(p) { return "#/p/" + encodeURIComponent(p.id); }
  function go(id) { location.hash = "#/p/" + encodeURIComponent(id); }

  const median = (xs) => {
    const v = xs.filter((x) => x != null && !Number.isNaN(x)).sort((a, b) => a - b);
    if (!v.length) return null;
    const m = Math.floor(v.length / 2);
    return v.length % 2 ? v[m] : (v[m - 1] + v[m]) / 2;
  };
  const num = (v) => (typeof v === "boolean" ? +v : v);

  function peersOf(p) {
    const sameRole = DATA.politicos.filter((x) => x.rol === p.rol);
    const sameLeague = sameRole.filter((x) => x.liga === p.liga);
    // the engine falls back to the whole role when a league is too small
    return sameLeague.length === p.grupo_pares ? sameLeague : sameRole;
  }

  function history(p) {
    const same = p.codigo ? (x) => x.codigo === p.codigo && x.rol === p.rol : (x) => x.nombre === p.nombre && x.rol === p.rol;
    return DATA.politicos.filter(same).sort((a, b) => String(b.periodo).localeCompare(String(a.periodo)));
  }

  function pctClass(pc) {
    return pc == null ? "r-na" : pc >= 80 ? "r-great" : pc >= 60 ? "r-good" : pc >= 40 ? "r-avg" : pc >= 20 ? "r-poor" : "r-bad";
  }

  function renderPerson(id) {
    const p = BY_ID.get(id);
    const el = $("#view-person");
    if (!p) {
      el.innerHTML = `<div class="crumbs"><a href="#/">← Volver al listado</a></div><div class="panel pad">No encontramos a este político (id: ${esc(id)}).</div>`;
      return;
    }
    const role = CFG.roles[p.rol];
    const peers = peersOf(p);
    const rated = DATA.politicos.filter((x) => x.rol === p.rol && x.rating != null);
    document.title = `${p.nombre} · Integridad Política`;

    const tiles = [
      [p.rol === "alcalde" || p.rol === "gobernador" ? "Departamento" : "Partido",
        `<b class="tile-txt">${esc(p.rol === "alcalde" || p.rol === "gobernador" ? p.departamento : p.partido)}</b>`],
      ["Puesto en " + role.label.toLowerCase(), p.rank_rol ? `<b class="tile-num">${p.rank_rol}</b><span class="src"> de ${rated.length}</span>` : "–"],
      ["Puesto en su grupo", p.rank_liga ? `<b class="tile-num">${p.rank_liga}</b><span class="src"> · ${esc(grupo(p.liga))}</span>` : `<span class="src">${esc(grupo(p.liga))}</span>`],
      p.rating_principal === "integridad"
        ? ["Eventos registrados", `<b class="tile-num">${p.integridad.n_eventos}</b><span class="src">${p.integridad.resta_total ? " · resta −" + p.integridad.resta_total.toFixed(1) : ""}</span>`]
        : ["Cobertura de datos", `<b class="tile-num">${Math.round(p.cobertura * 100)}%</b>`],
    ].map(([k, v]) => `<div class="tile"><div class="tile-k">${esc(k)}</div><div class="tile-v">${v}</div></div>`).join("");

    const cats = Object.entries(role.categories).map(([k, c]) => {
      const r = p.categorias[k].rating;
      return `<div class="bar"><div class="lbl"><span>${esc(c.label)}</span><span class="src">peso ${Math.round(c.weight * 100)}%</span></div>
        <div class="v">${r == null ? "–" : r.toFixed(2)}</div><div class="track"><div class="fill ${tier(r)}" style="width:${r == null ? 0 : r * 10}%"></div></div></div>`;
    }).join("");

    const statRows = Object.entries(role.metrics).map(([k, m]) => {
      const e = p.metricas[k];
      const med = median(peers.map((x) => num(x.metricas[k] && x.metricas[k].valor)));
      const src = (p.fuentes && p.fuentes[k]) || m.source;
      return `<tr class="${e.valor == null ? "missing" : ""}">
        <td class="l">${esc(m.label)}${m.direction < 0 ? ' <span class="src" title="Menor es mejor">↓ mejor</span>' : ""}<div class="src">${esc(role.categories[m.category].label)}</div></td>
        <td><b>${fmt(e.valor, m.unit)}</b></td>
        <td class="src">${med == null ? "–" : fmt(m.unit === "bool" ? med >= 0.5 : med, m.unit)}</td>
        <td class="l pc-cell">${e.percentil == null ? '<span class="na">sin dato</span>'
          : `<div class="pc"><div class="track"><div class="fill ${pctClass(e.percentil)}" style="width:${e.percentil}%"></div></div><span>P${Math.round(e.percentil)}</span></div>`}</td>
        <td class="l src small">${esc(src)}</td></tr>`;
    }).join("");

    const lab = (k) => esc(role.metrics[k].label);
    const hist = history(p);
    const histHtml = hist.length > 1 ? `<section class="panel pad"><h3>Historial</h3><table class="mini"><thead><tr><th class="l">Mandato</th><th class="l">Años con datos</th><th class="l">Titular</th><th>Rating</th></tr></thead><tbody>
      ${hist.map((h) => `<tr class="${h.id === p.id ? "sel" : ""}"><td class="l"><a href="${personHref(h)}">${esc(h.periodo || "–")}</a></td><td class="l">${esc((h.anios || []).join(", ") || "–")}</td><td class="l">${esc(h.titular_identificado === false ? "—" : h.nombre)}</td><td>${badge(h.rating)}</td></tr>`).join("")}
      </tbody></table></section>` : "";

    let neigh = "";
    if (p.rank_rol) {
      const sorted = rated.slice().sort((a, b) => b.rating - a.rating);
      const i = sorted.findIndex((x) => x.id === p.id);
      const near = sorted.slice(Math.max(0, i - 3), i + 4);
      neigh = `<section class="panel pad"><h3>Posiciones cercanas en el ranking</h3><ol class="near">
        ${near.map((x) => `<li class="${x.id === p.id ? "me" : ""}"><span class="pos">${sorted.indexOf(x) + 1}</span><a class="who-row" href="${personHref(x)}">${avatar(x)}<span class="near-name">${esc(x.nombre)}<span class="src">${esc(x.partido && x.partido !== "—" ? x.partido : x.entidad || "")}</span></span></a>${badge(x.rating)}</li>`).join("")}
      </ol></section>`;
    }

    el.innerHTML = `
      <div class="crumbs"><a href="#/" data-back>← ${esc(role.label)}</a>
        <a class="rect-btn" href="${rectHref(p)}" target="_blank" rel="noopener noreferrer">¿Encontraste un error? Solicitar rectificación</a></div>
      <section class="hero panel ${verdict(p)}">
        ${avatar(p, "hero")}
        <div class="hero-txt">
          <span class="hero-kicker">Expediente</span>
          <div class="src">${esc(role.position)}${p.periodo ? " · mandato " + esc(p.periodo) : ""}${p.anios && p.anios.length ? " · datos de " + esc(p.anios.join(", ")) : ""}</div>
          <h1>${esc(p.nombre)}</h1>
          <div class="hero-sub">${subtitle(p)}</div>
        </div>
        <div class="hero-rating">${badge(p.rating, "huge")}<div class="src">${p.rating == null ? "sin rating global" : p.rating_principal === "integridad" ? "nota de integridad" : "nota del mandato"}</div></div>
      </section>

      ${p.titular_identificado === false ? `<div class="note">Titular aún no vinculado: se califica el cargo en el mandato ${esc(p.periodo || "")}.</div>` : ""}
      ${p.rating == null ? `<div class="note">Sin rating global: cobertura ${Math.round(p.cobertura * 100)}% &lt; ${Math.round(CFG.rating.min_coverage * 100)}% mínimo de datos para dar una nota confiable. Las categorías con datos sí se muestran.</div>` : ""}

      <div class="tiles">${tiles}</div>

      <div class="person-grid">
        <div class="col-main">
          ${ledgerHtml(p)}
          <section class="panel pad">
            <h3>${p.rating_principal === "integridad" ? "Actividad legislativa (informativa, no cuenta en la nota)" : "Estadísticas"} <span class="src">· comparado con ${peers.length} pares (grupo: ${esc(grupo(p.liga))})</span></h3>
            <div class="table-wrap"><table class="stats">
              <thead><tr><th class="l">Métrica</th><th>Valor</th><th>Mediana pares</th><th class="l">Percentil</th><th class="l">Fuente</th></tr></thead>
              <tbody>${statRows}</tbody></table></div>
            ${p.extra ? `<p class="src">Impedimentos declarados en plenaria: <b>${p.extra.impedimentos_declarados_plenaria}</b> · se revisaron ${p.extra.proyectos_revisados} proyectos y ${p.extra.plenarias_revisadas} plenarias.</p>` : ""}
            ${p.secop ? `<p class="src">SECOP ${esc((p.secop.anios || p.anios || []).join(", "))}: ${p.secop.contratos.toLocaleString("es-CO")} contratos${p.secop.contratos_secop1 ? ` (${p.secop.contratos_secop1.toLocaleString("es-CO")} en SECOP I)` : ""}, ${p.secop.procesos_competitivos} procesos competitivos.</p>` : ""}
          </section>
          ${histHtml}
        </div>
        <div class="col-side">
          ${p.perfil ? `<section class="panel pad"><h3>Perfil</h3>
            ${p.perfil.descripcion ? `<p class="src">${esc(p.perfil.descripcion)}</p>` : ""}
            <p>${esc(p.perfil.extracto || "")}</p>
            <p class="src small-legend">Fuente secundaria: <a href="${esc(p.perfil.url)}" target="_blank" rel="noopener noreferrer">Wikipedia — ${esc(p.perfil.titulo)}</a>${p.perfil.editado ? ` (editado ${esc(String(p.perfil.editado).slice(0, 10))})` : ""}. Útil para contexto; los hechos de integridad se toman de las fuentes primarias que cita.</p>
          </section>` : ""}
          <section class="panel pad"><h3>Categorías</h3>${cats}</section>
          <section class="panel pad">
            <h3>Fortalezas</h3>${p.fortalezas.length ? `<div class="tags">${p.fortalezas.map((k) => `<span class="tag s">${lab(k)}</span>`).join("")}</div>` : '<p class="src">Ninguna destacada (≥ P80).</p>'}
            <h3>Debilidades</h3>${p.debilidades.length ? `<div class="tags">${p.debilidades.map((k) => `<span class="tag w">${lab(k)}</span>`).join("")}</div>` : '<p class="src">Ninguna marcada (≤ P20).</p>'}
          </section>
          ${neigh}
        </div>
      </div>
      ${debateHtml(p)}`;
    mountGiscus(p);

    el.querySelector("[data-back]").onclick = (e) => {
      e.preventDefault();
      if (state.role !== p.rol) {
        Object.assign(state, { role: p.rol, view: "resumen", liga: "", partido: "" });
      }
      location.hash = "#/";
    };
    window.scrollTo(0, 0);
  }


  function ledgerHtml(p) {
    const I = p.integridad;
    if (!I) return "";
    if (p.rating_principal !== "integridad" && !I.n_eventos) return "";   // performance roles: show ledger only if it has events
    const lvCfg = (CFG.integridad && CFG.integridad.niveles) || {};
    const legend = Object.entries(lvCfg).filter(([k]) => k !== "4").map(([k, v]) => `<span class="lv lv${k}">N${k}</span> ${esc(v.label)} (−${v.resta})`).join(" · ");
    if (!I.n_eventos) {
      return `<section class="panel pad"><h3>Integridad</h3>
        <p>Sin hallazgos registrados, ni en contra ni a favor: queda en la base (${CFG.integridad.base}). <span class="src">Esto no certifica ausencia de problemas: significa que la bitácora aún no tiene eventos documentados para esta persona. Para subir a 10 hay que demostrar transparencia (P1–P3).</span></p>
        <p class="src small-legend">${legend}</p>
        <a class="btn-aportar" href="${aportarHref(p)}" target="_blank" rel="noopener noreferrer">+ Aportar evidencia sobre esta persona</a></section>`;
    }
    const items = I.eventos.map((e) => `
      <article class="ev ${e.positivo ? "ev-pos" : ""}">
        <div class="ev-head">
          ${e.positivo ? `<span class="lv lvpos" title="${esc(e.nivel_label)}">${esc(e.tipo_positivo)}</span>` : `<span class="lv lv${e.nivel}" title="${esc(e.nivel_label)}">N${e.nivel}</span>`}
          <span class="chip">${esc(ESTADO_LABEL[e.estado] || e.estado)}</span>
          ${e.fecha ? `<span class="src">${esc(e.fecha)}</span>` : ""}
          ${e.positivo ? `<span class="ev-resta pos">+${(e.suma || 0).toFixed(2).replace(/0$/, "")}</span>` : `<span class="ev-resta">${e.resta ? "−" + e.resta.toFixed(1) : "no resta"}</span>`}
        </div>
        <h4 class="ev-title">${esc(e.titulo)}</h4>
        <p>${esc(e.resumen)}</p>
        ${e.rectificaciones && e.rectificaciones.length ? `<p class="ev-note"><b>Rectificación:</b> ${e.rectificaciones.map(esc).join(" ")}</p>` : ""}
        ${e.respuesta ? `<p class="ev-note"><b>Respuesta / versión del político:</b> ${esc(e.respuesta)}</p>` : ""}
        <ul class="ev-src">${e.fuentes.map((f) => `<li><a href="${esc(f.url)}" target="_blank" rel="noopener noreferrer">${esc(f.medio || "Fuente")}${f.fecha ? " · " + esc(f.fecha) : ""}</a>${f.titulo ? ` — <span class="src">${esc(f.titulo)}</span>` : ""}</li>`).join("")}</ul>
        ${e.aportado_por ? `<p class="src">Aportado por ${e.aportado_por.url ? `<a href="${esc(e.aportado_por.url)}" target="_blank" rel="noopener noreferrer">${esc(e.aportado_por.usuario || "un ciudadano")}</a>` : esc(e.aportado_por.usuario || "un ciudadano anónimo")} · gracias por contribuir</p>` : ""}
        ${e.revisado ? "" : '<span class="chip warn">Pendiente de revisión editorial</span>'}
      </article>`).join("");
    const posLegend = Object.entries((CFG.integridad && CFG.integridad.positivos) || {}).map(([k, v]) => `<span class="lv lvpos">${k}</span> ${esc(v.label)} (+${v.suma})`).join(" · ");
    return `<section class="panel pad"><h3>Integridad <span class="src">· base ${CFG.integridad.base} · ${I.n_negativos || 0} en contra (−${I.resta_total.toFixed(1)}) · ${I.n_positivos || 0} a favor (+${(I.suma_total || 0).toFixed(2)})</span></h3>
      ${items}<p class="src small-legend">${legend}<br>${posLegend} (tope +${CFG.integridad.tope_positivos}).<br>Presunción de inocencia: un proceso abierto no es una condena.</p>
      <a class="btn-aportar" href="${aportarHref(p)}" target="_blank" rel="noopener noreferrer">+ Aportar evidencia sobre esta persona</a></section>`;
  }

  function debateHtml(p) {
    const aportar = `<a class="btn-aportar" href="${aportarHref(p)}" target="_blank" rel="noopener noreferrer">+ Aportar evidencia</a>`;
    return `<section class="panel pad debate" id="debate">
      <h3>Debate ciudadano</h3>
      <p class="src">Opina con respeto y con argumentos. Los comentarios no cambian la nota: para eso aporta evidencia con fuentes,
        que el equipo revisa. Se eliminan insultos, amenazas, datos personales y desinformación.</p>
      ${aportar}
      <div class="giscus-slot">${GISCUS.categoryId ? "" : '<p class="note">Los comentarios se activarán pronto.</p>'}</div>
    </section>`;
  }

  function mountGiscus(p) {
    if (!GISCUS.categoryId) return;
    const slot = document.querySelector("#debate .giscus-slot");
    if (!slot) return;
    const sc = document.createElement("script");
    sc.src = "https://giscus.app/client.js";
    const attrs = {
      "data-repo": GISCUS.repo, "data-repo-id": GISCUS.repoId, "data-category": GISCUS.category,
      "data-category-id": GISCUS.categoryId, "data-mapping": "specific", "data-term": "Expediente: " + p.id,
      "data-strict": "1", "data-reactions-enabled": "1", "data-emit-metadata": "0", "data-input-position": "top",
      "data-theme": "preferred_color_scheme", "data-lang": "es", "data-loading": "lazy", crossorigin: "anonymous",
    };
    Object.entries(attrs).forEach(([k, v]) => sc.setAttribute(k, v));
    sc.async = true;
    slot.appendChild(sc);
  }

  // ================================================================ router
  function route() {
    const m = location.hash.match(/^#\/p\/(.+)$/);
    const isPerson = !!m;
    $("#view-list").hidden = isPerson;
    $("#view-person").hidden = !isPerson;
    if (isPerson) {
      renderPerson(decodeURIComponent(m[1]));
    } else {
      document.title = "Integridad Política Colombiana";
      render();
    }
  }
  window.addEventListener("hashchange", route);

  route();
})();
