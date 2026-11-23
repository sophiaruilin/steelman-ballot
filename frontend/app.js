// Steelman Ballot frontend. Plain JavaScript, no libraries, no third-party requests.
// Every piece of card text goes in with textContent (never innerHTML), so source text can't run as code.
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";
const store = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
// A new visit starts blank. The last ballot (districts and card list only, never the address)
// stays on this device and comes back with one tap: "Show my last ballot".
let state = { ballot: null, saved: store.get("sb.ballot", null), lang: store.get("sb.lang", null) || guessLang() };

// ---- language (English, Spanish, Simplified Chinese) -------------------------------------
function guessLang() {
  const l = (navigator.language || "en").toLowerCase();
  return l.startsWith("es") ? "es" : l.startsWith("zh") ? "zh" : "en";
}
function t(key, vars = {}) {
  const dict = (window.I18N || {})[state.lang] || {};
  let s = dict[key] ?? (window.I18N?.en || {})[key] ?? key;
  for (const [k, v] of Object.entries(vars)) s = s.replace(`{${k}}`, v);
  return s;
}
function applyLang() {
  document.documentElement.lang = { en: "en", es: "es", zh: "zh-Hans" }[state.lang];
  document.querySelectorAll("[data-i18n]").forEach((n) => { n.textContent = t(n.dataset.i18n); });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => { n.placeholder = t(n.dataset.i18nPlaceholder); });
  document.querySelectorAll("[data-langblock]").forEach((n) => { n.hidden = n.dataset.langblock !== state.lang; });
  document.querySelectorAll("[data-setlang]").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.setlang === state.lang)));
}
function setLang(lang) {
  state.lang = lang;
  store.set("sb.lang", lang);
  applyLang();
  captionMap();
  if ($("#ready-hint")) updateHint();
  route();
}

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat(2)) if (kid !== null && kid !== undefined && kid !== false)
    n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return n;
}
// replaceChildren() turns null into the text "null"; fill() skips empty slots.
const fill = (node, ...kids) => node.replaceChildren(...kids.flat(2).filter((k) => k !== null && k !== undefined && k !== false));
// Text the server sends in English (labels, office names): translated when we have it, otherwise left as is.
const tx = (en) => { if (!en || state.lang === "en") return en; const v = t(`srv:${en}`); return v === `srv:${en}` ? en : v; };
// "Prop 1" / "Question 2" / "Proposal 3" in the voter's language
function numLabel(n) {
  const m = /^(Prop|Question|Proposal)\s+(\d+)$/i.exec(n || "");
  return m ? t(`num.${m[1].toLowerCase()}`, { n: m[2] }) : n;
}
const mTitle = (m) => (m.titles && m.titles[state.lang]) || m.plain_title;
// District names from the Census, e.g. "Congressional District 12", "State Senate District 8", "Sacramento city"
function txDistrict(d) {
  if (!d || state.lang === "en") return d;
  const zh = state.lang === "zh";
  const rules = [[/^Congressional District (\d+)$/, zh ? "第$1国会选区" : "Distrito del Congreso $1"],
    [/^State Senate District (\d+)$/, zh ? "州参议院第$1选区" : "Distrito $1 del Senado estatal"],
    [/^(?:State House|State Assembly|Assembly) District (\d+)$/, zh ? "州众议院第$1选区" : "Distrito $1 de la Cámara estatal"],
    [/^U\.S\. House ([A-Z]{2})-(\d+)$/, zh ? "美国众议院 $1-$2" : "Cámara de EE. UU. $1-$2"],
    [/^(.*) city$/, zh ? "$1市" : "Ciudad de $1"], [/^(.*) County$/, zh ? "$1县" : "Condado de $1"]];
  for (const [re, out] of rules) if (re.test(d)) return d.replace(re, out);
  return tx(d);
}
function svg(tag, attrs = {}, ...kids) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return n;
}
const REPORT_FORM = "https://docs.google.com/forms/d/e/1FAIpQLSdEMz4oFJH_zGy1xtdHiAsf12pKQJD1jVn4ktJWbIQTBfQvKw/viewform";
const REPORT_FIELD = "entry.1541200026";   // "Which card?" (pre-filled so reporters don't have to type it)
const reportUrl = (label) => `${REPORT_FORM}?usp=pp_url&${REPORT_FIELD}=${encodeURIComponent(label)}`;
const reportLink = (label) => el("p", { class: "report" },
  el("a", { href: reportUrl(label), target: "_blank", rel: "noopener noreferrer" }, t("card.report")));
const safeUrl = (u) => (/^https:\/\//i.test(u || "") ? u : null);
const extLink = (url, text) => safeUrl(url)
  ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, text || new URL(url).hostname) : (text || "");
const status = (msg) => { $("#status").textContent = msg || ""; };
// Join a short list the way each language does: "A, B, and C." / "A, B y C." / "A、B和C。"
const sentence = (xs) => {
  const lang = state.lang;
  const v = (xs || []).map((x, i) => (i && lang !== "zh" ? x.charAt(0).toLowerCase() + x.slice(1) : x).replace(/[.。]$/, ""));
  if (!v.length) return "";
  let s;
  try { s = new Intl.ListFormat({ en: "en-US", es: "es", zh: "zh-CN" }[lang] || "en-US", { style: "long", type: "conjunction" }).format(v); }
  catch { s = v.length > 2 ? `${v.slice(0, -1).join(", ")}, and ${v.at(-1)}` : v.join(" and "); }
  return s + (lang === "zh" ? "。" : ".");
};

async function api(path) {
  const r = await fetch(path, { headers: { Accept: "application/json" } });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}

// ---- the balance mark (same for every card: neither side is favored) ----------------------
function scaleIcon(cls = "") {
  return svg("svg", { viewBox: "0 0 48 48", "aria-hidden": "true", class: cls, fill: "none", stroke: "#234742", "stroke-width": "1.6", "stroke-linecap": "round", "stroke-linejoin": "round" },
    svg("path", { d: "M24 8v30M16 40h16M8 14h32" }),
    svg("circle", { cx: "24", cy: "8", r: "2", fill: "#AD7857", stroke: "none" }),
    svg("path", { d: "M8 14l-5 10h10zM40 14l-5 10h10z" }),
    svg("path", { d: "M3 24q5 4 10 0M35 24q5 4 10 0", stroke: "#AD7857" }));
}

// ---- coverage map: equal-area tile grid (every state the same size) ---------------------------
const TILES = {
  AK: [0, 0], ME: [0, 11],
  VT: [1, 10], NH: [1, 11],
  WA: [2, 1], ID: [2, 2], MT: [2, 3], ND: [2, 4], MN: [2, 5], WI: [2, 6], MI: [2, 8], NY: [2, 9], MA: [2, 10], RI: [2, 11],
  OR: [3, 1], NV: [3, 2], WY: [3, 3], SD: [3, 4], IA: [3, 5], IL: [3, 6], IN: [3, 7], OH: [3, 8], PA: [3, 9], NJ: [3, 10], CT: [3, 11],
  CA: [4, 1], UT: [4, 2], CO: [4, 3], NE: [4, 4], MO: [4, 5], KY: [4, 6], WV: [4, 7], VA: [4, 8], MD: [4, 9], DE: [4, 10],
  AZ: [5, 2], NM: [5, 3], KS: [5, 4], AR: [5, 5], TN: [5, 6], NC: [5, 7], SC: [5, 8], DC: [5, 9],
  OK: [6, 4], LA: [6, 5], MS: [6, 6], AL: [6, 7], GA: [6, 8],
  HI: [7, 0], TX: [7, 4], FL: [7, 9],
};
const STATE_NAMES = { CA: "California", MA: "Massachusetts", NY: "New York" };

let mapCovered = {};
function captionMap() {
  const c = $("#map-caption");
  if (c) c.textContent = Object.entries(mapCovered).map(([k, v]) => `${tx(STATE_NAMES[k] || k)}: ${tx(v)}`).join(" · ");
}
async function renderMap() {
  let covered = {}, kinds = {};
  try { const cov = await api("/api/coverage"); covered = cov.states; kinds = cov.kinds || {}; }
  catch { covered = { CA: "", MA: "", NY: "", CT: "" }; kinds = { CA: "full", MA: "full", NY: "part", CT: "checked" }; }
  const S = 46, G = 4;
  const root = svg("svg", { viewBox: `0 0 ${12 * (S + G)} ${8 * (S + G)}`, role: "img", "aria-labelledby": "map-title map-desc" },
    svg("desc", { id: "map-desc" }, `Covered: ${Object.keys(covered).map((k) => STATE_NAMES[k] || k).join(", ")}.`),
    svg("defs", {}, svg("pattern", { id: "hatch", width: "6", height: "6", patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
      svg("rect", { width: "6", height: "6", fill: "#F3E9E1" }), svg("line", { x1: "0", y1: "0", x2: "0", y2: "6", stroke: "#AD7857", "stroke-width": "2.2" }))));
  for (const [st, [r, c]] of Object.entries(TILES)) {
    const kind = st in covered ? (kinds[st] || "full") : "";
    const g = svg("g", {}, svg("title", {}, st in covered ? `${STATE_NAMES[st] || st}: ${covered[st]}` : `${st}: coming later`));
    g.append(svg("rect", { x: c * (S + G), y: r * (S + G), width: S, height: S, rx: 2, class: `tile ${kind}` }));
    g.append(svg("text", { x: c * (S + G) + S / 2, y: r * (S + G) + S / 2, class: kind ? `lbl-${kind}` : "" }, st));
    root.append(g);
  }
  fill($("#usmap"), root);
  mapCovered = covered;
  captionMap();
}

// ---- ballot ------------------------------------------------------------------------------------
let lookupSeq = 0;
const lookupBusy = () => !$("#progress").hidden;
const STEPS = ["districts", "guide", "cards"];
const PCT = { districts: [5, 30], guide: [35, 85], cards: [88, 100] };   // start/done percent per step

function progress(open) {
  const box = $("#progress");
  box.hidden = !open;
  if (!open) return;
  $("#prog-title").textContent = t("prog.title");
  $("#prog-hint").hidden = true;
  setBar(2);
  fill($("#prog-steps"), ...STEPS.map((id) => el("li", { id: `ps-${id}`, class: "pstep" },
    el("span", { class: "mark", "aria-hidden": "true" }, "○"), el("span", { class: "plabel" }, t(`prog.${id}`)),
    el("span", { class: "pmeta muted" }, ""))));
}
function setBar(pct) {
  $("#prog-fill").style.width = `${pct}%`;
  $("#progress .bar").setAttribute("aria-valuenow", String(Math.round(pct)));
}
function stepUpdate(d) {
  const li = $(`#ps-${d.id}`);
  if (!li) return;
  if (d.id === "guide" && d.source !== undefined) {
    li.querySelector(".plabel").textContent = d.source ? `${t("prog.guide")}: ${d.source}` : t("prog.guide_none");
  }
  if (d.state === "start") {
    li.className = "pstep active"; li.querySelector(".mark").textContent = "◐";
    setBar(PCT[d.id][0]);
  } else {
    li.className = "pstep done"; li.querySelector(".mark").textContent = "✓";
    const bits = [];
    if (d.count !== undefined) bits.push(t("prog.found", { n: d.count }));
    if (d.seconds !== undefined) bits.push(`${d.seconds}s`);
    li.querySelector(".pmeta").textContent = bits.join(" · ");
    setBar(PCT[d.id][1]);
  }
}

function renderLastBallotLink() {
  const box = $("#last-ballot");
  const show = !state.ballot && state.saved;
  box.hidden = !show;
  if (!show) return;
  const city = (state.saved.districts?.City || "").replace(/ (city|town|village|borough|CDP)$/i, "");
  const where = [city, state.saved.state].filter(Boolean).join(", ");
  fill(box, el("button", { type: "button", class: "linkish", onclick: () => {
    state.ballot = state.saved;
    renderBallot(); $("#ballot").hidden = false; box.hidden = true;
    compactHero(true);
  } }, t("last.show", { where })),
  " · ",
  el("button", { type: "button", class: "linkish muted", onclick: () => {
    store.set("sb.ballot", null); state.saved = null; box.hidden = true;
  } }, t("last.forget")));
}

// Once someone looks up a ballot, the intro steps aside: only the address box stays above the result.
function compactHero(on) {
  $(".hero").classList.toggle("compact", on);
  if (on) window.scrollTo({ top: 0 });
}

function showBallotData(b, mine) {
  if (mine !== lookupSeq) return;          // a newer lookup started while this one was loading
  state.ballot = b;
  const { matched_address, ...keep } = b;  // the matched address is shown once, never saved
  state.saved = keep;
  store.set("sb.ballot", keep);            // districts and card list only; the address is not saved
  $("#last-ballot").hidden = true;
  status("");
  setBar(100);
  setTimeout(() => { if (mine === lookupSeq) progress(false); }, 500);
  renderBallot();
  $("#ballot").hidden = false;
  compactHero(true);
}

async function postJSON(path, body) {
  return fetch(path, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json" },
                       body: JSON.stringify(body) });
}

async function lookup(address) {
  const mine = ++lookupSeq;                // only the most recent lookup may update the screen
  state.ballot = null;
  $("#ballot").hidden = true;              // never leave the previous address's ballot showing
  status("");
  compactHero(true);
  progress(true);
  const slow = setTimeout(() => { if (mine === lookupSeq) { $("#prog-hint").hidden = false; $("#prog-hint").textContent = t("prog.slow"); } }, 7000);
  const fail = (msg) => { if (mine !== lookupSeq) return; clearTimeout(slow); progress(false); status(msg); };
  const done = (b) => { clearTimeout(slow); showBallotData(b, mine); };
  // The address goes in the request body (POST), never in a URL, so it isn't kept in history or logs.
  try {
    const res = await postJSON("/api/ballot/stream", { address });
    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      return fail(res.status === 422 ? t("help.min") : (err.error || `Request failed (${res.status})`));
    }
    if (!res.body || !res.body.getReader) {           // very old in-app browsers: no streaming
      return done(await (await postJSON("/api/ballot", { address })).json());
    }
    const reader = res.body.getReader();
    const dec = new TextDecoder();
    let buf = "", finished = false;
    while (!finished) {
      const { value, done: end } = await reader.read();
      if (end) break;
      buf += dec.decode(value, { stream: true });
      let i;
      while ((i = buf.indexOf("\n\n")) >= 0) {
        const block = buf.slice(0, i); buf = buf.slice(i + 2);
        const kind = (block.match(/^event: (.+)$/m) || [])[1];
        const data = JSON.parse((block.match(/^data: (.+)$/m) || [, "{}"])[1]);
        if (kind === "step" && mine === lookupSeq) stepUpdate(data);
        else if (kind === "fail") { finished = true; fail(data.message); }
        else if (kind === "ballot") { finished = true; done(data); }
      }
    }
  } catch (e) {
    fail(e.message || t("prog.slow"));
  }
}

function coveragePill(name, v) {
  const cls = { official: "ok", none_on_ballot: "ok", not_mapped: "warn", unavailable: "warn", needs_address: "" }[v] || "";
  const txt = t(`cov.${v}`);
  return el("li", { class: `pill ${cls}` }, `${tx(name)}: ${txt}`);
}

const LOCALE = { en: "en-US", es: "es-US", zh: "zh-CN" };
const fmtDate = (iso) => new Intl.DateTimeFormat(LOCALE[state.lang] || "en-US", { dateStyle: "long", timeZone: "UTC" })
  .format(new Date(`${iso}T00:00:00Z`));
// Which measure cards this browser has opened. Kept only on this device; no vote is ever recorded.
const readIds = () => new Set(store.get("sb.read") || []);
function markRead(id) { const r = readIds(); if (!r.has(id)) { r.add(id); store.set("sb.read", [...r]); } }

// "1315 10TH ST, SACRAMENTO, CA, 95814" -> "1315 10th St, Sacramento, CA 95814"
function prettyAddress(a) {
  const cap = (x) => x.toLowerCase().replace(/(^|[\s-])([a-z])/g, (m, p, c) => p + c.toUpperCase());
  const parts = a.split(/\s*,\s*/);
  if (parts.length < 4) return a;
  const [street, city, st, zip] = parts;
  return `${cap(street)}, ${cap(city)}, ${st.toUpperCase()} ${zip}`;
}

function renderBallot() {
  const b = state.ballot;
  const d = b.districts;
  const districtLine = [d["Congress"], d["State Senate"], d["State House / Assembly"], d["City"]].filter(Boolean).map(txDistrict).join(" · ");
  const ready = b.races.filter((r) => r.status === "ready" && r.id);
  const rest = b.races.filter((r) => !(r.status === "ready" && r.id));
  // If the voter typed a ZIP and the Census matched a different one, say so: it may be the wrong place.
  const typedZip = (/\b(\d{5})(?:-\d{4})?\s*$/.exec($("#address").value.trim()) || [])[1];
  const matchedZip = (/(\d{5})(?:-\d{4})?\s*$/.exec(b.matched_address || "") || [])[1];
  const zipOff = typedZip && matchedZip && typedZip !== matchedZip ? [typedZip, matchedZip] : null;
  fill($("#summary"), 
    el("p", { class: "eyebrow" }, `${b.state} · ${t("ballot.election")} ${fmtDate(b.election)}`),
    el("h2", {}, t("ballot.title")),
    b.matched_address ? el("div", { class: `matched${zipOff ? " off" : ""}` },
      el("span", { class: "ok", "aria-hidden": "true" }, zipOff ? "⚠ " : "✓ "), `${t("ballot.matched")}: `, el("b", {}, prettyAddress(b.matched_address)), " · ",
      editButton(t("ballot.edit")),
      zipOff ? el("p", { class: "zip-off" }, t("ballot.zipdiff", { a: zipOff[0], b: zipOff[1] })) : null) : null,
    el("div", { class: "stats" },
      b.covered_state === false
        ? el("span", { class: "no-races" }, t("ballot.measuresnot"))
        : el("span", {}, el("b", {}, b.measures.length), t(b.measures.length === 1 ? "ballot.measure" : "ballot.measures")),
      ready.length
        ? el("span", {}, el("b", {}, ready.length), t(ready.length === 1 ? "ballot.race" : "ballot.races"),
          rest.length ? el("small", { class: "more-races" }, t("ballot.morerace", { n: rest.length })) : null)
        : el("span", { class: "no-races" }, t("ballot.racesnot"))),
    b.zip_only ? el("div", { class: "notice" }, t("ballot.ziponly"), " ", editButton(t("ballot.change")))
      : el("p", { class: "districts-line" }, districtLine),
    el("p", { class: "notice" }, t("ballot.notice"), " ", b.official_links.map((l) => [extLink(l.url, tx(l.label)), " "])),
    b.measures.some((m) => m.status === "ready")
      ? el("p", { class: "start-here" }, t("ballot.start"), el("span", { class: "arrow-down", "aria-hidden": "true" }, "↓"))
      : null,
    el("details", {},
      el("summary", {}, t("ballot.details")),
      el("p", { class: "muted" }, tx(b.coverage_note || "")),
      el("ul", { class: "pills", "aria-label": t("ballot.coverage") }, Object.entries(b.coverage).map(([k, v]) => coveragePill(k, v))),
      b.election_passed ? el("p", { class: "muted" }, t("ballot.lookback", { d: fmtDate(b.election) })) : null));
  const measures = b.measures;   // official ballot order
  fill($("#measures"), ...(measures.length ? measures.map((m) => el("li", {}, listItem(m), m.status === "ready" ? previewToggle(m) : null))
    : [el("li", { class: "uncovered" }, t(b.covered_state === false ? "ballot.notstate" : "ballot.none"))]));
  fill($("#races"), 
    ready.length ? ready.map((r) => el("li", {}, raceItem(r))) : el("li", { class: "uncovered" }, t("ballot.noraces")),
    rest.length ? el("li", { class: "uncovered" }, el("b", {}, ready.length ? t("ballot.notcovered", { n: rest.length }) : t("ballot.alsoon")), " ",
      rest.map((r) => txDistrict(r.office)).join(" · ")) : null);
}

// "Not right? Edit": open a small address box right here, instead of sending the voter back to the top.
function editButton(label) {
  return el("button", { type: "button", class: "linkish", onclick: (e) => {
    const host = e.currentTarget.closest(".matched, .notice");
    const hint = el("span", { class: "ready-hint", "aria-live": "polite" });
    const input = el("input", { type: "text", value: $("#address").value, "aria-label": t("form.label"), autocomplete: "off",
      spellcheck: "false", minlength: "5", maxlength: "200", required: true, placeholder: t("form.placeholder") });
    const form = el("form", { class: "edit-address", onsubmit: (ev) => {
      ev.preventDefault();
      const v = input.value.trim();
      if (v.length < 5) return;
      $("#address").value = v; updateHint(); lookup(v);
    } }, input, el("button", { type: "submit", class: "btn" }, t("ballot.update")),
      el("button", { type: "button", class: "btn ghost", onclick: () => renderBallot() }, t("ballot.cancel")), hint);
    const check = () => showHint(addressHint(input.value), hint);
    input.addEventListener("input", check);
    host.after(form); host.hidden = true;
    check(); input.focus(); input.select();
  } }, label);
}

// "Preview both sides": the two one-line steelmen, right in the ballot list
function previewToggle(m) {
  const sides = (m.sides && (m.sides[state.lang] || m.sides.en)) || null;
  if (!sides) return null;
  const box = el("div", { class: "preview", hidden: true },
    el("div", { class: "pair2" },
      el("div", { class: "col col-no" }, el("p", { class: "vote-h" }, t("card.against")), el("p", {}, sides.no)),
      el("div", { class: "col col-yes" }, el("p", { class: "vote-h" }, t("card.for")), el("p", {}, sides.yes))),
    el("p", {}, el("a", { href: `#card=${m.id}` }, t("item.open"))));
  const btn = el("button", { type: "button", class: "linkish peek", "aria-expanded": "false", onclick: () => {
    box.hidden = !box.hidden; btn.setAttribute("aria-expanded", String(!box.hidden));
    btn.textContent = box.hidden ? t("item.peek") : t("item.peek_close");
  } }, t("item.peek"));
  return [btn, box];
}

function listItem(m) {
  if (m.status !== "ready") {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, numLabel(m.number)),
      el("span", { class: "ttl" }, m.official_title), el("span", { class: "meta" }, t("item.pending"), m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, tx(m.scope)) : null));
  }
  return el("button", { class: "item", onclick: () => go(`card=${m.id}`) },
    el("span", { class: "num" }, numLabel(m.number)), el("span", { class: "ttl" }, mTitle(m)),
    el("span", { class: "meta" },
      el("span", { class: "cta" }, t("item.cta")),
      m.verified ? null : el("span", { class: "pill warn" }, t("item.unverified")),
      `· ${m.reading_minutes} ${t("item.read")}`,
      readIds().has(m.id) ? el("span", { class: "pill done" }, `✓ ${t("item.done")}`) : null,
      m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, tx(m.scope)) : null));
}

function raceItem(r) {
  const label = { not_researched: t("item.pending"), check_official_ballot: t("item.maybe") }[r.status];
  if (r.status !== "ready" || !r.id) {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, tx(r.level)), el("span", { class: "ttl" }, txDistrict(r.office)), el("span", { class: "meta" }, label));
  }
  return el("button", { class: "item", onclick: () => go(`card=${r.id}`) },
    el("span", { class: "num" }, tx(r.level)), el("span", { class: "ttl" }, tx(r.office)), el("span", { class: "meta" }, r.candidates.join(" · ")));
}

// ---- routing -------------------------------------------------------------------------------------
const VIEWS = ["home", "card", "how"];
function go(hash) { location.hash = hash || ""; }
window.addEventListener("hashchange", route);

function show(view) {
  for (const v of VIEWS) $(`#view-${v}`).hidden = v !== view;
  document.querySelectorAll(".nav a").forEach((a) => a.toggleAttribute("aria-current", a.dataset.route === view));
  document.querySelectorAll(".nav a[aria-current]").forEach((a) => a.setAttribute("aria-current", "page"));
}

async function route() {
  const h = location.hash.slice(1);
  const id = (h.match(/^card=([A-Za-z0-9-]+)$/) || [])[1];
  // About, Steelman and Philosophy now live on the How it works page; old links still land there.
  if (["about", "steelman", "philosophy"].includes(h)) { history.replaceState(null, "", "#how"); return route(); }
  if (h === "how") { show("how"); window.scrollTo(0, 0); return; }
  if (h === "never") {
    show("how");
    setTimeout(() => { const u = [...document.querySelectorAll("#view-how .nevers")].find((x) => x.offsetParent); const d = u?.closest("details"); if (d) d.open = true; (d || u)?.scrollIntoView({ behavior: "instant", block: "start" }); }, 50);
    return;
  }
  if (h === "idea") { show("home"); renderLastBallotLink(); setTimeout(() => $("#idea").scrollIntoView(), 0); return; }
  if (h === "map") { show("home"); renderLastBallotLink(); setTimeout(() => $("#map-title").scrollIntoView(), 0); return; }
  if (!id) {
    show("home");
    $(".hero").classList.toggle("compact", !!state.ballot || lookupBusy());
    if (state.ballot) { $("#ballot").hidden = false; renderBallot(); }
    renderLastBallotLink();
    return;
  }
  show("card");
  const box = $("#view-card");
  fill(box, el("p", { class: "status" }, t("status.loading")));
  try {
    const rec = await api(`/api/card/${encodeURIComponent(id)}?lang=${state.lang}`);
    const isMeasure = "steelman_yes" in rec.card;
    box.replaceChildren(...[backButton(), isMeasure ? measureCard(rec) : raceCard(rec), isMeasure ? cardNav(id) : null].filter(Boolean));
    if (isMeasure) markRead(id);
  } catch (e) {
    fill(box, backButton(), el("p", { class: "status" }, e.message));
  }
  window.scrollTo(0, 0);
}
// Previous / next measure on this ballot, so a voter can read straight through without going back each time.
function cardNav(id) {
  const list = ((state.ballot || state.saved)?.measures || []).filter((m) => m.status === "ready");
  const i = list.findIndex((m) => m.id === id);
  if (i < 0 || list.length < 2) return null;
  const prev = list[i - 1], next = list[i + 1];
  const link = (m, dir) => el("button", { class: `navcard ${dir}`, onclick: () => go(`card=${m.id}`) },
    el("span", { class: "dir" }, dir === "prev" ? `← ${t("nav.prev")}` : `${t("nav.next")} →`),
    el("span", { class: "nt" }, `${numLabel(m.number)}: ${mTitle(m)}`));
  return el("nav", { class: "card-nav", "aria-label": t("nav.cards") },
    prev ? link(prev, "prev") : el("span", {}), next ? link(next, "next") : el("span", {}),
    el("p", { class: "muted pos" }, t("nav.pos", { i: i + 1, n: list.length })));
}
const backButton = () => el("p", { class: "back" }, el("button", { class: "btn ghost", onclick: () => go("") }, t("card.back")));

// ---- measure card ---------------------------------------------------------------------------------
function claimLi(c) {
  const tag = t(`tag.${c.label}`) + (c.whose && c.label !== "fact" ? ` · ${c.whose}` : "");
  return el("li", {}, el("span", { class: `tag ${c.label}` }, tag), c.text, " ",
    el("span", { class: "src" }, "[", extLink(c.source_url, t("card.source")), "]"));
}
const notGiven = (s) => !s || /^(not (specified|identified|stated)|unknown)/i.test(s.trim());

function reasoningPanel(kind, s) {
  return el("section", { class: "reasoning", hidden: true, "aria-label": `Reasoning: the case ${kind}` },
    el("p", { class: "label" }, `${t("card.reasoning")} · ${t(kind === "for" ? "card.for" : "card.against")}`),
    el("p", { class: "headline-lg" }, s.headline),
    s.basis === "no_organized_side" ? el("p", { class: "basis" }, t("card.nobasis")) : null,
    s.more_reasons.length ? [el("h4", {}, t("card.more")), el("ul", {}, s.more_reasons.map((r) => el("li", {}, r)))] : null,
    el("h4", {}, t("card.evidence")), el("ul", {}, s.best_evidence.map(claimLi)),
    el("h4", {}, t("card.helps")), el("p", {}, s.who_it_helps),
    el("h4", {}, t("card.answer")), el("p", {}, s.answer_to_other_side));
}

function side(kind, s, panel) {
  const btn = el("button", { class: "explore", "aria-expanded": "false", onclick: () => {
    panel.hidden = !panel.hidden;
    btn.setAttribute("aria-expanded", String(!panel.hidden));
    btn.textContent = panel.hidden ? t("card.explore") : t("card.close");
    if (!panel.hidden) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } }, t("card.explore"));
  return el("section", { class: "side", "aria-label": t(kind === "for" ? "card.for" : "card.against") },
    el("p", { class: "label" }, t(kind === "for" ? "card.for" : "card.against")),
    el("p", { class: "values" }, sentence(s.values) || s.headline),
    el("p", { class: "headline" }, s.headline),
    btn);
}

// Readable names for official source pages ("Nonpartisan analysis" instead of a long web address)
function srcLabel(u) {
  const pdf = /\.pdf.*pages=(\d+)-(\d+)/i.exec(u);
  if (pdf) return t("src.pdf", { a: pdf[1], b: pdf[2] });
  if (/\.pdf/i.test(u)) return t("src.pdfall");
  if (/title-summary/.test(u)) return t("src.summary");
  if (/analysis/.test(u)) return t("src.analysis");
  if (/arguments/.test(u)) return t("src.args");
  if (/nycvotes\.org/.test(u)) return /ballot-proposal-\d/.test(u) ? t("src.nycone") : t("src.nycall");
  try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return u; }
}

// A collapsible section: a one-line label you can open for the detail
const fold = (id, label, ...kids) => el("details", { class: "fold", id },
  el("summary", {}, label), el("div", { class: "fold-body" }, ...kids));

function measureCard(rec) {
  const c = rec.card;
  // One fixed rule for the whole card, tied to the vote: LEFT = No (against, today),
  // RIGHT = Yes (for, if it passes). It matches the Today -> If it passes arrow and never flips,
  // even for referendums where a Yes vote keeps an existing law.
  const pFor = reasoningPanel("for", c.steelman_yes), pAgainst = reasoningPanel("against", c.steelman_no);
  const left = side("against", c.steelman_no, pAgainst), right = side("for", c.steelman_yes, pFor);
  const col = (kind, ...kids) => el("div", { class: `col col-${kind}` }, ...kids);
  const facts = [c.fiscal_impact, ...c.evidence].filter(Boolean);
  const jump = (id, label) => el("a", { href: `#${id}`, onclick: (e) => {
    e.preventDefault(); const d = document.getElementById(id); if (d && d.tagName === "DETAILS") d.open = true;
    d?.scrollIntoView({ behavior: "smooth", block: "start" }); } }, label);
  const art = el("article", { class: "measure" });
  // View menu: both sides, or one side at a time (the other column is hidden everywhere on the card)
  const view = el("select", { "aria-label": t("card.view"), onchange: (e) => {
    art.classList.toggle("only-yes", e.target.value === "yes");
    art.classList.toggle("only-no", e.target.value === "no");
  } }, el("option", { value: "both" }, t("card.view_both")), el("option", { value: "no" }, t("card.view_no")),
    el("option", { value: "yes" }, t("card.view_yes")));

  fill(art,
    el("header", { class: "card-head" },
      el("p", { class: "eyebrow" }, numLabel(c.number)),
      el("h1", {}, c.plain_title),
      el("ul", { class: "pills" },
        el("li", { class: `pill ${rec.steelman_verified ? "ok" : "warn"}` }, rec.steelman_verified ? t("card.checked") : t("card.unverified")),
        el("li", { class: "pill" }, `${c.reading_minutes} ${t("card.min")}`)),
      state.lang !== "en" ? el("p", { class: "notice" }, rec.lang === state.lang ? t("card.translated") : t("card.notyet")) : null,
      IN_WECHAT ? el("p", { class: "wx-tip" }, t("share.wx_tip")) : null),

    el("nav", { class: "card-menu", "aria-label": t("card.jump") },
      el("label", {}, `${t("card.view")} `, view),
      el("span", { class: "jumps" }, `${t("card.jump")}${state.lang === "zh" ? "：" : ": "}`,
        jump("c-short", t("card.short")), " · ", jump("c-sides", t("card.sides_s")), " · ",
        jump("c-changes", t("card.changes")), " · ", jump("c-facts", t("card.facts_s")), " · ",
        jump("c-sources", t("card.dig_s")), " · ", jump("c-vote", t("vote.h")))),

    // 1. The short version: what a yes and a no would actually do
    el("section", { class: "short", id: "c-short" },
      el("h2", {}, t("card.short")),
      el("div", { class: "pair2" },
        col("no", el("p", { class: "vote-h" }, t("card.no")), el("p", {}, c.no_means)),
        col("yes", el("p", { class: "vote-h" }, t("card.yes")), el("p", {}, c.yes_means)))),

    // 2. Each side at its strongest, then their other reasons, in the same two columns
    el("section", { id: "c-sides" },
      el("h2", { class: "sr-heading" }, t("three.2h")),
      el("div", { class: "balance" }, left, el("div", { class: "fulcrum" }, scaleIcon()), right),
      [pAgainst, pFor],
      (c.steelman_no.more_reasons.length || c.steelman_yes.more_reasons.length) ? el("div", { class: "pair2 reasons" },
        col("no", el("p", { class: "vote-h" }, t("card.more")), el("ul", {}, c.steelman_no.more_reasons.map((r) => el("li", {}, r)))),
        col("yes", el("p", { class: "vote-h" }, t("card.more")), el("ul", {}, c.steelman_yes.more_reasons.map((r) => el("li", {}, r))))) : null),

    // 3. The one point they really disagree on
    el("div", { class: "crux" }, el("b", {}, t("card.crux")), c.crux.text),

    // 4. Detail, one tap away
    fold("c-changes", `${t("card.changes")} (${c.what_changes.length})`,
      el("div", { class: "changes" },
        el("div", { class: "changes-head" }, el("span", {}, t("card.today")), el("span", {}, ""), el("span", {}, t("card.ifpasses"))),
        c.what_changes.map((r) => el("div", { class: "change" },
          el("div", { class: "topic" }, r.topic),
          el("div", { class: "flow" },
            el("div", { class: "now" }, el("span", { class: "lbl" }, t("card.today")), r.today),
            el("div", { class: "arrow", "aria-hidden": "true" }, "→"),
            el("div", { class: "then" }, el("span", { class: "lbl" }, t("card.ifpasses")), r.if_passes,
              r.label === "prediction" ? el("span", { class: "muted" }, ` (${t("tag.prediction")} · ${r.whose || "?"})`) : null, " ",
              el("span", { class: "src" }, "[", extLink(r.source_url, t("card.source")), "]"))))))),
    fold("c-facts", `${t("card.facts")} (${facts.length})`, el("ul", { class: "evidence" }, facts.map(claimLi))),
    fold("c-affected", `${t("card.affected")} (${c.who_is_affected.length})`,
      el("ul", { class: "affected" }, c.who_is_affected.map((w) => el("li", {}, w)))),

    // 5. Where to read more, by name
    el("section", { class: "dig", id: "c-sources" }, el("h2", {}, t("card.dig")),
      el("ul", { class: "sources" }, (rec.sources || []).map((u) => el("li", {}, extLink(u, srcLabel(u)))))),

    // 6. What to do next
    el("div", { id: "c-vote" }, howToVote(c)),
    shareBar(c.measure_id, c),
    el("p", { class: "official" }, `${t("card.official")}: `, c.official_title, c.title_disputed ? " · ⚖" : "",
      notGiven(c.put_on_ballot_by) ? "" : ` · ${t("card.placed")}: ${tx(c.put_on_ballot_by)}`),
    reportLink(`${c.number}: ${c.plain_title} (${c.measure_id})`),
    el("p", { class: "muted" }, t("card.rule")));
  return art;
}

// The practical next step, the same for every Yes/No measure. Never which way to vote.
function howToVote(c) {
  const day = (/(\d{4}-\d{2}-\d{2})/.exec(c.measure_id || "") || [])[1];
  const past = day && new Date(`${day}T23:59:59`) < new Date();
  return el("section", { class: "how-to-vote" }, el("h2", {}, t("vote.h")),
    el("ul", {}, el("li", {}, t("vote.1")), el("li", {}, t("vote.2")),
      el("li", {}, t("vote.3"), " ", extLink("https://vote.gov/", "vote.gov"))),
    past ? el("p", { class: "muted" }, t("vote.past")) : null);
}

// ---- race card ------------------------------------------------------------------------------------
function raceCard(rec) {
  const c = rec.card;
  return el("article", {},
    el("header", { class: "card-head" }, el("p", { class: "eyebrow" }, t("race.label")), el("h1", {}, tx(c.office)),
      el("p", {}, el("b", {}, `${t("race.does")}: `), c.what_office_does.text, " ",
        el("span", { class: "src" }, "[", extLink(c.what_office_does.source_url, t("card.source")), "]")),
      el("p", { class: "muted" }, rec.ballot_order_note || "Candidates in official ballot order.")),
    el("div", { class: "cands" }, c.candidates.map((p) => el("section", { class: "cand" },
      el("h3", {}, p.name), el("p", { class: "party" }, tx(p.party)),
      p.says_basis === "none_found"
        ? el("p", {}, t("race.nostatement"))
        : [el("p", { class: "values" }, p.headline || ""), el("p", {}, p.core_case), el("ul", {}, p.says.map(claimLi))],
      ))),
    c.where_they_differ ? el("div", { class: "crux" }, el("b", {}, t("race.differ")), c.where_they_differ.text) : null,
    el("section", { class: "learn-more" }, el("h3", {}, t("race.more")),
      el("ul", {},
        (rec.sources || []).slice(0, 1).map((u) => el("li", {}, extLink(u, t("race.statements")))),
        c.race_id.startsWith("CA-") ? el("li", {}, extLink("https://cal-access.sos.ca.gov/Campaign/Candidates/", t("race.money"))) : null,
        el("li", {}, extLink("https://vote.gov/", t("race.office"))))),
    el("p", { class: "muted" }, t("race.note")),
    reportLink(`${c.office} (${c.race_id})`));
}

// ---- sharing (always both sides) --------------------------------------------------------------
// ---- WeChat: a ready-to-send image (title + QR with our logo + how to open it) -----------------------
const IN_WECHAT = /MicroMessenger/i.test(navigator.userAgent);
const loadImg = (src) => new Promise((ok, bad) => { const i = new Image(); i.onload = () => ok(i); i.onerror = bad; i.src = src; });
// Wrap text to a width: Chinese can break between any two characters, other languages between words.
function wrapLines(ctx, text, maxW, maxLines) {
  const tokens = text.match(/[\u3000-\u9fff\uff00-\uffef]|[^\s\u3000-\u9fff\uff00-\uffef]+|\s+/g) || [];
  const lines = []; let line = "";
  for (const tok of tokens) {
    const next = line + tok;
    if (ctx.measureText(next.trimEnd()).width > maxW && line.trim()) { lines.push(line.trim()); line = tok.trimStart(); }
    else line = next;
  }
  if (line.trim()) lines.push(line.trim());
  if (lines.length > maxLines) { lines.length = maxLines; lines[maxLines - 1] = lines[maxLines - 1].replace(/.$/, "…"); }
  return lines;
}
async function wechatPoster(id, c, url) {
  const W = 720, H = 1060, cv = document.createElement("canvas");
  cv.width = W; cv.height = H;
  const x = cv.getContext("2d");
  await document.fonts.ready;
  const [qr, logo] = await Promise.all([loadImg(`/api/qr/${encodeURIComponent(id)}.svg`), loadImg("/icon.svg")]);
  const serif = '"EB Garamond", "Noto Serif SC", "Songti SC", "SimSun", serif';
  const sans = '"IBM Plex Sans", "PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif';
  x.fillStyle = "#F4F0E7"; x.fillRect(0, 0, W, H);
  // header band with the logo and name
  x.fillStyle = "#234742"; x.fillRect(0, 0, W, 112);
  x.drawImage(logo, 40, 26, 60, 60);
  x.fillStyle = "#F4F0E7"; x.font = `600 40px ${serif}`; x.textBaseline = "middle"; x.fillText("Steelman Ballot", 118, 58);
  // which measure, in the reader's language
  x.textBaseline = "alphabetic";
  x.fillStyle = "#885E44"; x.font = `600 26px ${sans}`; x.fillText(numLabel(c.number), 48, 172);
  x.fillStyle = "#2B3031"; x.font = `600 38px ${serif}`;
  let y = 222;
  for (const ln of wrapLines(x, c.plain_title, W - 96, 3)) { x.fillText(ln, 48, y); y += 50; }
  // the QR, with our logo in the middle (the code uses high error correction, so it still scans)
  const Q = 420, qx = (W - Q) / 2, qy = Math.max(y + 24, 330);
  x.fillStyle = "#FFFFFF"; x.fillRect(qx - 18, qy - 18, Q + 36, Q + 36);
  x.strokeStyle = "#A9B0AB"; x.lineWidth = 2; x.strokeRect(qx - 18, qy - 18, Q + 36, Q + 36);
  x.imageSmoothingEnabled = false; x.drawImage(qr, qx, qy, Q, Q); x.imageSmoothingEnabled = true;
  const L = 84; x.fillStyle = "#FFFFFF"; x.fillRect(W / 2 - L / 2 - 8, qy + Q / 2 - L / 2 - 8, L + 16, L + 16);
  x.drawImage(logo, W / 2 - L / 2, qy + Q / 2 - L / 2, L, L);
  // how to open it
  y = qy + Q + 76;
  x.fillStyle = "#234742"; x.font = `600 32px ${sans}`; x.textAlign = "center";
  for (const ln of wrapLines(x, t("share.poster_caption"), W - 96, 2)) { x.fillText(ln, W / 2, y); y += 44; }
  x.fillStyle = "#5F6663"; x.font = `400 22px ${sans}`;
  x.fillText(t("share.poster_note"), W / 2, y + 10);
  x.fillText(url.replace(/^https?:\/\//, ""), W / 2, H - 36);
  x.textAlign = "start";
  return cv.toDataURL("image/png");
}

function shareBar(id, c) {
  const out = el("p", { class: "status", role: "status" });
  const qrBox = el("div", { class: "qr", hidden: true });
  const copy = async (text, msg) => {
    try { await navigator.clipboard.writeText(text); out.textContent = msg; }
    catch { out.textContent = t("share.copyfail"); }
  };
  const getShare = (ch = "") => api(`/api/share/${encodeURIComponent(id)}${ch ? `?ch=${ch}` : ""}`);
  return el("section", {}, el("h3", {}, t("share.title")),
    IN_WECHAT ? el("p", { class: "wx-tip" }, t("share.wx_tip")) : null,
    el("div", { class: "share" },
      el("button", { class: "btn", onclick: async () => { const s = await getShare("whatsapp"); location.href = s.whatsapp_link; } }, "WhatsApp"),
      el("button", { class: "btn", onclick: async () => {
        const s = await getShare("wechat"); await copy(s.wechat, t("share.wechat_copied"));
        fill(qrBox, el("p", { class: "muted" }, t("status.loading"))); qrBox.hidden = false;
        try {
          const png = await wechatPoster(id, c, s.url || "");
          fill(qrBox, el("img", { class: "poster", src: png, alt: t("share.poster_alt") }),
            el("div", {}, el("p", {}, t("share.poster_help")),
              el("a", { class: "btn ghost", href: png, download: `steelman-ballot-${id}.png` }, t("share.save")),
              el("p", { class: "muted qr-link" }, `${t("share.link")} `, s.url || "")));
        } catch {                                  // very old browsers: fall back to the plain QR code
          fill(qrBox, el("img", { src: `/api/qr/${encodeURIComponent(id)}.svg`, alt: t("share.qr_alt"), width: "180", height: "180" }),
            el("div", {}, el("p", {}, t("share.qr_help")), el("p", { class: "muted qr-link" }, `${t("share.link")} `, s.url || "")));
        }
      } }, "WeChat"),
      navigator.share ? el("button", { class: "btn ghost", onclick: async () => {
        const s = await getShare("more"); try { await navigator.share({ title: "Steelman Ballot", text: s.plain }); } catch { /* cancelled */ }
      } }, t("share.more")) : null,
      el("button", { class: "btn ghost", onclick: async () => { const s = await getShare("copy"); copy(s.url, t("share.copied")); } }, t("share.copy"))),
    qrBox, out);
}

// ---- address hint (runs on this device only; nothing is sent while typing) ---------------------------
const STATE_CODES = new Set(("AL AK AZ AR CA CO CT DE DC FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA RI SC SD TN TX UT VT VA WA WV WI WY").split(" "));
const STATE_NAME_END = /(alabama|alaska|arizona|arkansas|california|colorado|connecticut|delaware|florida|georgia|hawaii|idaho|illinois|indiana|iowa|kansas|kentucky|louisiana|maine|maryland|massachusetts|michigan|minnesota|mississippi|missouri|montana|nebraska|nevada|new hampshire|new jersey|new mexico|new york|north carolina|north dakota|ohio|oklahoma|oregon|pennsylvania|rhode island|south carolina|south dakota|tennessee|texas|utah|vermont|virginia|washington|west virginia|wisconsin|wyoming)$/i;
function addressHint(v) {
  v = v.trim();
  if (/^\d{5}(-\d{4})?$/.test(v)) return { ok: true, key: "form.ziponly" };
  if (!/^\d+[a-z]?\s+\S+/i.test(v)) return null;                 // not a street address yet
  const words = v.replace(/[.,]/g, " ").split(/\s+/).filter(Boolean);
  const last = words[words.length - 1] || "";
  const complete = words.length >= 4 && (/^\d{5}(-\d{4})?$/.test(last) || STATE_CODES.has(last.toUpperCase()) || STATE_NAME_END.test(v.replace(/[.,]+$/, "")));
  return complete ? { ok: true, key: "form.ready" } : { ok: false, key: "form.addcity" };
}
function showHint(h, box) {
  box.className = `ready-hint${h ? (h.ok ? " ok" : " todo") : ""}`;
  box.textContent = h ? `${h.ok ? "✓ " : ""}${t(h.key)}` : "";
}
function updateHint() { showHint(addressHint($("#address").value), $("#ready-hint")); }
$("#address").addEventListener("input", updateHint);

// ---- start -----------------------------------------------------------------------------------------
$("#address-form").addEventListener("submit", (e) => { e.preventDefault(); lookup($("#address").value.trim()); });
document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => {
  $("#address").value = b.dataset.example; lookup(b.dataset.example);
}));
document.querySelectorAll("[data-setlang]").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.setlang)));
applyLang();
renderMap();
route();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
