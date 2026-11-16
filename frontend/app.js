// Steelman Ballot frontend. Plain JavaScript, no libraries, no third-party requests.
// Every piece of card text goes in with textContent (never innerHTML), so source text can't run as code.
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";
const store = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
let state = { ballot: store.get("sb.ballot", null), lang: store.get("sb.lang", null) || guessLang() };

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
function svg(tag, attrs = {}, ...kids) {
  const n = document.createElementNS(SVGNS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined) n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return n;
}
const safeUrl = (u) => (/^https:\/\//i.test(u || "") ? u : null);
const extLink = (url, text) => safeUrl(url)
  ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, text || new URL(url).hostname) : (text || "");
const status = (msg) => { $("#status").textContent = msg || ""; };
const sentence = (xs) => {
  const v = (xs || []).map((x, i) => (i ? x.charAt(0).toLowerCase() + x.slice(1) : x));
  const s = v.length > 2 ? `${v.slice(0, -1).join(", ")}, and ${v.at(-1)}` : v.join(" and ");
  return s ? s.replace(/\.$/, "") + "." : "";
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
const STATE_NAMES = { CA: "California", MA: "Massachusetts", NY: "New York", CT: "Connecticut" };

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
  $("#usmap").replaceChildren(root);
  $("#map-caption").textContent = Object.entries(covered).map(([k, v]) => `${STATE_NAMES[k] || k}: ${v}`).join(" · ");
}

// ---- ballot ------------------------------------------------------------------------------------
let lookupSeq = 0;
const STEPS = ["districts", "guide", "cards"];
const PCT = { districts: [5, 30], guide: [35, 85], cards: [88, 100] };   // start/done percent per step

function progress(open) {
  const box = $("#progress");
  box.hidden = !open;
  if (!open) return;
  $("#prog-title").textContent = t("prog.title");
  $("#prog-hint").hidden = true;
  setBar(2);
  $("#prog-steps").replaceChildren(...STEPS.map((id) => el("li", { id: `ps-${id}`, class: "pstep" },
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

function showBallotData(b, mine) {
  if (mine !== lookupSeq) return;          // a newer lookup started while this one was loading
  state.ballot = b;
  store.set("sb.ballot", b);               // districts and card list only; the address is not saved
  status("");
  setBar(100);
  setTimeout(() => { if (mine === lookupSeq) progress(false); }, 500);
  renderBallot();
  $("#ballot").hidden = false;
  $("#ballot").scrollIntoView({ behavior: "smooth", block: "start" });
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
  return el("li", { class: `pill ${cls}` }, `${name}: ${txt}`);
}

function renderBallot() {
  const b = state.ballot;
  const d = b.districts;
  const districtLine = [d["Congress"], d["State Senate"], d["State House / Assembly"], d["City"]].filter(Boolean).join(" · ");
  $("#summary").replaceChildren(
    el("p", { class: "eyebrow" }, `${b.state} · ${t("ballot.election")} ${b.election}`),
    el("h2", {}, t("ballot.title")),
    el("div", { class: "stats" },
      el("span", {}, el("b", {}, b.measures.length), t("ballot.measures")),
      el("span", {}, el("b", {}, b.races.length), t("ballot.races"))),
    b.zip_only ? el("p", { class: "notice" }, t("ballot.ziponly")) : el("p", { class: "districts-line" }, districtLine),
    el("p", { class: "notice" }, t("ballot.notice"), " ", b.official_links.map((l) => [extLink(l.url, l.label), " "])),
    el("details", {},
      el("summary", {}, t("ballot.details")),
      el("p", { class: "muted" }, b.coverage_note || ""),
      el("ul", { class: "pills", "aria-label": t("ballot.coverage") }, Object.entries(b.coverage).map(([k, v]) => coveragePill(k, v))),
      b.election_passed ? el("p", { class: "muted" }, t("ballot.lookback", { d: b.election })) : null));
  const measures = b.measures;   // official ballot order
  $("#measures").replaceChildren(...(measures.length ? measures.map((m) => el("li", {}, listItem(m)))
    : [el("li", { class: "muted item disabled" }, el("span", {}), el("span", {}, t("ballot.none")))]));
  const ready = b.races.filter((r) => r.status === "ready" && r.id);
  const rest = b.races.filter((r) => !(r.status === "ready" && r.id));
  $("#races").replaceChildren(
    ...ready.map((r) => el("li", {}, raceItem(r))),
    rest.length ? el("li", { class: "uncovered" }, el("b", {}, t("ballot.notcovered", { n: rest.length })), " ",
      rest.map((r) => r.office).join(" · ")) : null);
}

function listItem(m) {
  if (m.status !== "ready") {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, m.number),
      el("span", { class: "ttl" }, m.official_title), el("span", { class: "meta" }, t("item.pending"), m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, m.scope) : null));
  }
  return el("button", { class: "item", onclick: () => go(`card=${m.id}`) },
    el("span", { class: "num" }, m.number), el("span", { class: "ttl" }, m.plain_title),
    el("span", { class: "meta" }, `${m.reading_minutes} ${t("item.read")}`,
      m.verified ? el("span", { class: "pill ok" }, t("item.checked")) : el("span", { class: "pill warn" }, t("item.unverified")),
      m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, m.scope) : null));
}

function raceItem(r) {
  const label = { not_researched: t("item.pending"), check_official_ballot: t("item.maybe") }[r.status];
  if (r.status !== "ready" || !r.id) {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, r.level), el("span", { class: "ttl" }, r.office), el("span", { class: "meta" }, label));
  }
  return el("button", { class: "item", onclick: () => go(`card=${r.id}`) },
    el("span", { class: "num" }, r.level), el("span", { class: "ttl" }, r.office), el("span", { class: "meta" }, r.candidates.join(" · ")));
}

// ---- routing -------------------------------------------------------------------------------------
const VIEWS = ["home", "card", "how", "steelman", "philosophy"];
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
  if (["how", "steelman", "philosophy"].includes(h)) { show(h); window.scrollTo(0, 0); return; }
  if (!id) {
    show("home");
    if (state.ballot) { $("#ballot").hidden = false; renderBallot(); }
    return;
  }
  show("card");
  const box = $("#view-card");
  box.replaceChildren(el("p", { class: "status" }, t("status.loading")));
  try {
    const rec = await api(`/api/card/${encodeURIComponent(id)}?lang=${state.lang}`);
    box.replaceChildren(backButton(), "steelman_yes" in rec.card ? measureCard(rec) : raceCard(rec));
  } catch (e) {
    box.replaceChildren(backButton(), el("p", { class: "status" }, e.message));
  }
  window.scrollTo(0, 0);
}
const backButton = () => el("p", { class: "back" }, el("button", { class: "btn ghost", onclick: () => go("") }, t("card.back")));

// ---- measure card ---------------------------------------------------------------------------------
function claimLi(c) {
  return el("li", {}, el("span", { class: "tag" }, c.label), c.text,
    c.whose ? el("span", { class: "muted" }, ` (${c.whose})`) : null, " ",
    el("span", { class: "src" }, "[", extLink(c.source_url, t("card.source")), "]"));
}

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

function measureCard(rec) {
  const c = rec.card;
  // One fixed rule for the whole card, tied to the vote: LEFT = No (against, today),
  // RIGHT = Yes (for, if it passes). It matches the Today -> If it passes arrow and never flips,
  // even for referendums where a Yes vote keeps an existing law.
  const pFor = reasoningPanel("for", c.steelman_yes), pAgainst = reasoningPanel("against", c.steelman_no);
  const left = side("against", c.steelman_no, pAgainst), right = side("for", c.steelman_yes, pFor);
  const vote = (word, text) => el("div", { class: "vote" },
    el("p", { class: "vote-h" }, scaleIcon("mini"), t(word === "yes" ? "card.yes" : "card.no")), el("p", {}, text));
  const vLeft = vote("no", c.no_means), vRight = vote("yes", c.yes_means);

  return el("article", {},
    el("header", { class: "card-head" },
      el("p", { class: "eyebrow" }, c.number),
      el("h1", {}, c.plain_title),
      el("ul", { class: "pills" },
        el("li", { class: `pill ${rec.steelman_verified ? "ok" : "warn"}` }, rec.steelman_verified ? t("card.checked") : t("card.unverified")),
        el("li", { class: "pill" }, `${c.reading_minutes} ${t("card.min")}`)),
      state.lang !== "en" ? el("p", { class: "notice" }, rec.lang === state.lang ? t("card.translated") : t("card.notyet")) : null),

    // 1. The headline takeaway: each side at its strongest, side by side
    el("h2", { class: "sr-heading" }, t("three.2h")),
    el("div", { class: "balance" }, left, el("div", { class: "fulcrum" }, scaleIcon()), right),
    [pAgainst, pFor],
    el("p", { class: "more-below" }, el("a", { href: "#details", onclick: (e) => { e.preventDefault(); $("#details").scrollIntoView({ behavior: "smooth" }); } },
      t("card.below"))),

    // 2. Details, for anyone who wants to go deeper
    el("div", { id: "details" },
      el("div", { class: "votes" }, vLeft, el("div", { class: "fulcrum thin" }, scaleIcon("mini")), vRight),
      el("h2", {}, t("card.changes")),
      el("div", { class: "changes" },
        el("div", { class: "changes-head" }, el("span", {}, t("card.today")), el("span", {}, ""), el("span", {}, t("card.ifpasses"))),
        c.what_changes.map((r) => el("div", { class: "change" },
          el("div", { class: "topic" }, r.topic),
          el("div", { class: "flow" },
            el("div", { class: "now" }, el("span", { class: "lbl" }, t("card.today")), r.today),
            el("div", { class: "arrow", "aria-hidden": "true" }, "→"),
            el("div", { class: "then" }, el("span", { class: "lbl" }, t("card.ifpasses")), r.if_passes,
              r.label === "prediction" ? el("span", { class: "muted" }, ` (${t("card.estimate")}: ${r.whose || "?"})`) : null, " ",
              el("span", { class: "src" }, "[", extLink(r.source_url, t("card.source")), "]")))))),
      el("div", { class: "crux" }, el("b", {}, t("card.crux")), c.crux.text),
      el("h2", {}, t("card.whatevidence")),
      el("ul", { class: "evidence" }, [c.fiscal_impact, ...c.evidence].filter(Boolean).map(claimLi)),
      el("h3", {}, t("card.affected")),
      el("ul", { class: "affected" }, c.who_is_affected.map((w) => el("li", {}, w))),
      el("p", { class: "official" }, `${t("card.official")}: `, c.official_title, c.title_disputed ? " · ⚖" : "",
        ` · ${t("card.placed")}: ${c.put_on_ballot_by}`),
      shareBar(c.measure_id),
      el("h3", {}, t("card.sources")),
      el("ul", { class: "sources" }, (rec.sources || []).map((u) => el("li", {}, extLink(u, u)))),
      el("p", { class: "muted" }, t("card.rule"))));
}

// ---- race card ------------------------------------------------------------------------------------
function raceCard(rec) {
  const c = rec.card;
  return el("article", {},
    el("header", { class: "card-head" }, el("p", { class: "eyebrow" }, t("race.label")), el("h1", {}, c.office),
      el("p", {}, el("b", {}, `${t("race.does")}: `), c.what_office_does.text, " ",
        el("span", { class: "src" }, "[", extLink(c.what_office_does.source_url, t("card.source")), "]")),
      el("p", { class: "muted" }, rec.ballot_order_note || "Candidates in official ballot order.")),
    el("div", { class: "cands" }, c.candidates.map((p) => el("section", { class: "cand" },
      el("h3", {}, p.name), el("p", { class: "party" }, p.party),
      p.says_basis === "none_found"
        ? el("p", {}, t("race.nostatement"))
        : [el("p", { class: "values" }, p.headline || ""), el("p", {}, p.core_case), el("ul", {}, p.says.map(claimLi))],
      el("p", { class: "muted" }, t("race.didfunded"))))),
    c.where_they_differ ? el("div", { class: "crux" }, el("b", {}, t("race.differ")), c.where_they_differ.text) : null,
    el("p", { class: "muted" }, t("race.note")));
}

// ---- sharing (always both sides) --------------------------------------------------------------
function shareBar(id) {
  const out = el("p", { class: "status", role: "status" });
  const qrBox = el("div", { class: "qr", hidden: true });
  const copy = async (text, msg) => {
    try { await navigator.clipboard.writeText(text); out.textContent = msg; }
    catch { out.textContent = t("share.copyfail"); }
  };
  const getShare = () => api(`/api/share/${encodeURIComponent(id)}`);
  return el("section", {}, el("h3", {}, t("share.title")),
    el("div", { class: "share" },
      el("button", { class: "btn", onclick: async () => { const s = await getShare(); location.href = s.whatsapp_link; } }, "WhatsApp"),
      el("button", { class: "btn", onclick: async () => {
        const s = await getShare(); await copy(s.wechat, t("share.wechat_copied"));
        qrBox.replaceChildren(el("img", { src: `/api/qr/${encodeURIComponent(id)}.svg`, alt: "QR code linking to this card" }));
        qrBox.hidden = false;
      } }, "WeChat"),
      navigator.share ? el("button", { class: "btn ghost", onclick: async () => {
        const s = await getShare(); try { await navigator.share({ title: "Steelman Ballot", text: s.plain }); } catch { /* cancelled */ }
      } }, t("share.more")) : null,
      el("button", { class: "btn ghost", onclick: async () => { const s = await getShare(); copy(s.url, t("share.copied")); } }, t("share.copy"))),
    qrBox, out);
}

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
