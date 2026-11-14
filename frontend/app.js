// Steelman Ballot frontend. Plain JavaScript, no libraries, no third-party requests.
// Every piece of card text goes in with textContent (never innerHTML), so source text can't run as code.
"use strict";

const $ = (sel) => document.querySelector(sel);
const SVGNS = "http://www.w3.org/2000/svg";
const store = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
let state = { ballot: store.get("sb.ballot", null) };

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
const STATE_NAMES = { CA: "California", MA: "Massachusetts", NY: "New York" };
const PARTIAL = new Set(["NY"]);   // local measures only (New York City)

async function renderMap() {
  let covered = {};
  try { covered = (await api("/api/coverage")).states; } catch { covered = { CA: "", MA: "", NY: "" }; }
  const S = 46, G = 4;
  const root = svg("svg", { viewBox: `0 0 ${12 * (S + G)} ${8 * (S + G)}`, role: "img", "aria-labelledby": "map-title map-desc" },
    svg("desc", { id: "map-desc" }, `Covered: ${Object.keys(covered).map((k) => STATE_NAMES[k] || k).join(", ")}.`),
    svg("defs", {}, svg("pattern", { id: "hatch", width: "6", height: "6", patternUnits: "userSpaceOnUse", patternTransform: "rotate(45)" },
      svg("rect", { width: "6", height: "6", fill: "#F3E9E1" }), svg("line", { x1: "0", y1: "0", x2: "0", y2: "6", stroke: "#AD7857", "stroke-width": "2.2" }))));
  for (const [st, [r, c]] of Object.entries(TILES)) {
    const kind = st in covered ? (PARTIAL.has(st) ? "part" : "full") : "";
    const g = svg("g", {}, svg("title", {}, st in covered ? `${STATE_NAMES[st] || st}: ${covered[st]}` : `${st}: coming later`));
    g.append(svg("rect", { x: c * (S + G), y: r * (S + G), width: S, height: S, rx: 2, class: `tile ${kind}` }));
    g.append(svg("text", { x: c * (S + G) + S / 2, y: r * (S + G) + S / 2, class: kind ? `lbl-${kind}` : "" }, st));
    root.append(g);
  }
  $("#usmap").replaceChildren(root);
  $("#map-caption").textContent = Object.entries(covered).map(([k, v]) => `${STATE_NAMES[k] || k}: ${v}`).join(" · ");
}

// ---- ballot ------------------------------------------------------------------------------------
async function lookup(address) {
  status("Finding your districts and ballot…");
  try {
    const b = await api(`/api/ballot?address=${encodeURIComponent(address)}`);
    state.ballot = b;
    store.set("sb.ballot", b);              // districts and card list only; the address is not saved
    status("");
    renderBallot();
    $("#ballot").hidden = false;
    $("#ballot").scrollIntoView({ behavior: "smooth", block: "start" });
  } catch (e) {
    status(e.message);
  }
}

function coveragePill(name, v) {
  const map = { official: ["ok", "from the official guide"], partial: ["", "partial"], not_mapped: ["warn", "not covered yet"],
                none_on_ballot: ["ok", "none on your ballot"], unavailable: ["warn", "temporarily unavailable"] };
  const [cls, txt] = map[v] || ["", v];
  return el("li", { class: `pill ${cls}` }, `${name}: ${txt}`);
}

function renderBallot() {
  const b = state.ballot;
  const ready = b.measures.filter((m) => m.status === "ready").length + b.races.filter((r) => r.status === "ready").length;
  $("#summary").replaceChildren(
    el("p", { class: "eyebrow" }, `${b.state} · Election of ${b.election}`),
    el("h2", {}, "Your ballot in 60 seconds"),
    el("div", { class: "stats" },
      el("span", {}, el("b", {}, b.measures.length), "ballot measures"),
      el("span", {}, el("b", {}, b.races.length), "races"),
      el("span", {}, el("b", {}, b.minutes_to_read), `minutes to read the ${ready} ready cards`)),
    el("ul", { class: "pills", "aria-label": "Your districts" }, Object.entries(b.districts).map(([k, v]) => el("li", { class: "pill" }, `${k}: ${v}`))),
    el("ul", { class: "pills", "aria-label": "Coverage" }, Object.entries(b.coverage).map(([k, v]) => coveragePill(k, v))),
    el("p", { class: "notice" }, b.coverage_note || ""),
    b.election_passed ? el("p", { class: "notice" }, `Look-back: this is the ${b.election} ballot as it stood before the vote. No results are shown.`) : null,
    el("p", { class: "notice" }, b.note, " ", b.official_links.map((l) => [extLink(l.url, l.label), " "])));
  const measures = b.measures;   // official ballot order
  $("#measures").replaceChildren(...(measures.length ? measures.map((m) => el("li", {}, listItem(m)))
    : [el("li", { class: "muted item disabled" }, el("span", {}), el("span", {}, "No ballot measures on your ballot in our sources."))]));
  $("#races").replaceChildren(...b.races.map((r) => el("li", {}, raceItem(r))));
}

function listItem(m) {
  if (m.status !== "ready") {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, m.number),
      el("span", { class: "ttl" }, m.official_title), el("span", { class: "meta" }, "Research pending", m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, m.scope) : null));
  }
  return el("button", { class: "item", onclick: () => go(`card=${m.id}`) },
    el("span", { class: "num" }, m.number), el("span", { class: "ttl" }, m.plain_title),
    el("span", { class: "meta" }, `${m.reading_minutes} min read`,
      m.verified ? el("span", { class: "pill ok" }, "Both sides checked") : el("span", { class: "pill warn" }, "Steelman unverified"),
      m.scope && m.scope !== "statewide" ? el("span", { class: "pill" }, m.scope) : null));
}

function raceItem(r) {
  const label = { not_researched: "Research pending", check_official_ballot: "May not be on your ballot: check your official sample ballot" }[r.status];
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
  box.replaceChildren(el("p", { class: "status" }, "Loading…"));
  try {
    const rec = await api(`/api/card/${encodeURIComponent(id)}`);
    box.replaceChildren(backButton(), "steelman_yes" in rec.card ? measureCard(rec) : raceCard(rec));
  } catch (e) {
    box.replaceChildren(backButton(), el("p", { class: "status" }, e.message));
  }
  window.scrollTo(0, 0);
}
const backButton = () => el("p", { class: "back" }, el("button", { class: "btn ghost", onclick: () => go("") }, "← Back to my ballot"));

// ---- measure card ---------------------------------------------------------------------------------
function claimLi(c) {
  return el("li", {}, el("span", { class: "tag" }, c.label), c.text,
    c.whose ? el("span", { class: "muted" }, ` (${c.whose})`) : null, " ",
    el("span", { class: "src" }, "[", extLink(c.source_url, "source"), "]"));
}

function reasoningPanel(kind, s) {
  return el("section", { class: "reasoning", hidden: true, "aria-label": `Reasoning: the case ${kind}` },
    el("p", { class: "label" }, `The reasoning · the case ${kind}`),
    el("p", { class: "headline-lg" }, s.headline),
    s.basis === "no_organized_side" ? el("p", { class: "basis" }, "No official argument was submitted for this side; this case comes from the official analysis.") : null,
    s.more_reasons.length ? [el("h4", {}, "More reasons"), el("ul", {}, s.more_reasons.map((r) => el("li", {}, r)))] : null,
    el("h4", {}, "Evidence they point to"), el("ul", {}, s.best_evidence.map(claimLi)),
    el("h4", {}, "Who it helps, in their view"), el("p", {}, s.who_it_helps),
    el("h4", {}, "Their answer to the other side"), el("p", {}, s.answer_to_other_side));
}

function side(kind, s, panel) {
  const btn = el("button", { class: "explore", "aria-expanded": "false", onclick: () => {
    panel.hidden = !panel.hidden;
    btn.setAttribute("aria-expanded", String(!panel.hidden));
    btn.textContent = panel.hidden ? "Explore reasoning →" : "Close reasoning ↑";
    if (!panel.hidden) panel.scrollIntoView({ behavior: "smooth", block: "nearest" });
  } }, "Explore reasoning →");
  return el("section", { class: "side", "aria-label": `The strongest case ${kind}` },
    el("p", { class: "label" }, `The strongest case ${kind}`),
    el("p", { class: "values" }, sentence(s.values) || s.headline),
    el("p", { class: "headline" }, s.headline),
    btn);
}

function measureCard(rec) {
  const c = rec.card;
  const yesFirst = (parseInt((c.number.match(/\d+/) || ["0"])[0], 10) % 2) === 1;   // alternate the order by number
  const pFor = reasoningPanel("for", c.steelman_yes), pAgainst = reasoningPanel("against", c.steelman_no);
  const sFor = side("for", c.steelman_yes, pFor), sAgainst = side("against", c.steelman_no, pAgainst);
  const [left, right] = yesFirst ? [sFor, sAgainst] : [sAgainst, sFor];
  const vote = (word, text) => el("div", { class: "vote" },
    el("p", { class: "vote-h" }, scaleIcon("mini"), `A ${word} vote means`), el("p", {}, text));
  const [vLeft, vRight] = yesFirst
    ? [vote("yes", c.yes_means), vote("no", c.no_means)] : [vote("no", c.no_means), vote("yes", c.yes_means)];

  return el("article", {},
    el("header", { class: "card-head" },
      el("p", { class: "eyebrow" }, c.number),
      el("h1", {}, c.plain_title),
      el("ul", { class: "pills" },
        el("li", { class: `pill ${rec.steelman_verified ? "ok" : "warn"}` }, rec.steelman_verified ? "Both sides checked by our fairness review" : "Steelman unverified: our fairness review still had notes"),
        el("li", { class: "pill" }, `${c.reading_minutes} min read`))),

    // 1. The headline takeaway: each side at its strongest, side by side
    el("h2", { class: "sr-heading" }, "Each side, at its strongest"),
    el("div", { class: "balance" }, left, el("div", { class: "fulcrum" }, scaleIcon()), right),
    yesFirst ? [pFor, pAgainst] : [pAgainst, pFor],
    el("p", { class: "more-below" }, el("a", { href: "#details", onclick: (e) => { e.preventDefault(); $("#details").scrollIntoView({ behavior: "smooth" }); } },
      "What a yes or no vote does, what would change, and the evidence ↓")),

    // 2. Details, for anyone who wants to go deeper
    el("div", { id: "details" },
      el("div", { class: "votes" }, vLeft, el("div", { class: "fulcrum thin" }, scaleIcon("mini")), vRight),
      el("h2", {}, "What would change"),
      el("div", { class: "changes" },
        el("div", { class: "changes-head" }, el("span", {}, "Today"), el("span", {}, ""), el("span", {}, "If it passes")),
        c.what_changes.map((r) => el("div", { class: "change" },
          el("div", { class: "topic" }, r.topic),
          el("div", { class: "flow" },
            el("div", { class: "now" }, el("span", { class: "lbl" }, "Today"), r.today),
            el("div", { class: "arrow", "aria-hidden": "true" }, "→"),
            el("div", { class: "then" }, el("span", { class: "lbl" }, "If it passes"), r.if_passes,
              r.label === "prediction" ? el("span", { class: "muted" }, ` (estimate: ${r.whose || "unattributed"})`) : null, " ",
              el("span", { class: "src" }, "[", extLink(r.source_url, "source"), "]")))))),
      el("div", { class: "crux" }, el("b", {}, `Where they really disagree · ${c.crux.kind}`), c.crux.text),
      el("h2", {}, "What the evidence says"),
      el("ul", { class: "evidence" }, [c.fiscal_impact, ...c.evidence].filter(Boolean).map(claimLi)),
      el("h3", {}, "Who is affected"),
      el("ul", { class: "affected" }, c.who_is_affected.map((w) => el("li", {}, w))),
      el("p", { class: "official" }, "Official title: ", c.official_title, c.title_disputed ? " · title challenged" : "",
        ` · Placed on ballot by: ${c.put_on_ballot_by}`),
      shareBar(c.measure_id),
      el("h3", {}, "Sources"),
      el("ul", { class: "sources" }, (rec.sources || []).map((u) => el("li", {}, extLink(u, u)))),
      el("p", { class: "muted" }, "Order alternates from measure to measure. Same space, same structure, same colors for both sides. We never tell you how to vote.")));
}

// ---- race card ------------------------------------------------------------------------------------
function raceCard(rec) {
  const c = rec.card;
  return el("article", {},
    el("header", { class: "card-head" }, el("p", { class: "eyebrow" }, "Race"), el("h1", {}, c.office),
      el("p", {}, el("b", {}, "What this office does: "), c.what_office_does.text, " ",
        el("span", { class: "src" }, "[", extLink(c.what_office_does.source_url, "source"), "]")),
      el("p", { class: "muted" }, rec.ballot_order_note || "Candidates in official ballot order.")),
    el("div", { class: "cands" }, c.candidates.map((p) => el("section", { class: "cand" },
      el("h3", {}, p.name), el("p", { class: "party" }, p.party),
      p.says_basis === "none_found"
        ? el("p", {}, "No statement submitted to the official voter guide.")
        : [el("p", { class: "values" }, p.headline || ""), el("p", {}, p.core_case), el("ul", {}, p.says.map(claimLi))],
      el("p", { class: "muted" }, "Did: no legislative record in our sources · Funded by: state campaign finance not connected yet")))),
    c.where_they_differ ? el("div", { class: "crux" }, el("b", {}, "Where they differ"), c.where_they_differ.text) : null,
    el("p", { class: "muted" }, "Statements were written by the candidates and not checked by any official agency. We never tell you how to vote."));
}

// ---- sharing (always both sides) --------------------------------------------------------------
function shareBar(id) {
  const out = el("p", { class: "status", role: "status" });
  const qrBox = el("div", { class: "qr", hidden: true });
  const copy = async (text, msg) => {
    try { await navigator.clipboard.writeText(text); out.textContent = msg; }
    catch { out.textContent = "Copy didn't work here. Press and hold the text to copy it."; }
  };
  const getShare = () => api(`/api/share/${encodeURIComponent(id)}`);
  return el("section", {}, el("h3", {}, "Share both sides"),
    el("div", { class: "share" },
      el("button", { class: "btn", onclick: async () => { const s = await getShare(); location.href = s.whatsapp_link; } }, "WhatsApp"),
      el("button", { class: "btn", onclick: async () => {
        const s = await getShare(); await copy(s.wechat, "Copied for WeChat: paste it into a chat, or let a friend scan the QR code.");
        qrBox.replaceChildren(el("img", { src: `/api/qr/${encodeURIComponent(id)}.svg`, alt: "QR code linking to this card" }));
        qrBox.hidden = false;
      } }, "WeChat"),
      navigator.share ? el("button", { class: "btn ghost", onclick: async () => {
        const s = await getShare(); try { await navigator.share({ title: "Steelman Ballot", text: s.plain }); } catch { /* cancelled */ }
      } }, "More…") : null,
      el("button", { class: "btn ghost", onclick: async () => { const s = await getShare(); copy(s.url, "Link copied."); } }, "Copy link")),
    qrBox, out);
}

// ---- start -----------------------------------------------------------------------------------------
$("#address-form").addEventListener("submit", (e) => { e.preventDefault(); lookup($("#address").value.trim()); });
document.querySelectorAll("[data-example]").forEach((b) => b.addEventListener("click", () => {
  $("#address").value = b.dataset.example; lookup(b.dataset.example);
}));
renderMap();
route();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
