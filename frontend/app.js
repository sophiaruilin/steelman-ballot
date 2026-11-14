// Steelman Ballot frontend. Plain JavaScript, no libraries, no third-party requests.
// Every piece of card text goes in with textContent (never innerHTML), so source text can't run as code.
"use strict";

const $ = (sel) => document.querySelector(sel);
const TOPICS = ["Housing", "Taxes", "Schools", "Health care", "Elections", "Environment", "Public safety", "State budget"];
const EXAMPLE = "1315 10th St, Sacramento, CA 95814";
const store = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch { return d; } },
  set: (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* private mode */ } },
};
let state = { ballot: store.get("sb.ballot", null), priorities: store.get("sb.priorities", []) };

function el(tag, attrs = {}, ...kids) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (v === null || v === undefined || v === false) continue;
    if (k === "class") n.className = v;
    else if (k.startsWith("on")) n.addEventListener(k.slice(2), v);
    else n.setAttribute(k, v === true ? "" : v);
  }
  for (const kid of kids.flat()) if (kid !== null && kid !== undefined && kid !== false)
    n.append(kid instanceof Node ? kid : document.createTextNode(String(kid)));
  return n;
}
const safeUrl = (u) => (/^https:\/\//i.test(u || "") ? u : null);
const extLink = (url, text) => safeUrl(url)
  ? el("a", { href: url, target: "_blank", rel: "noopener noreferrer" }, text || new URL(url).hostname) : text || "";
const status = (msg) => { $("#status").textContent = msg || ""; };

async function api(path) {
  const r = await fetch(path, { headers: { Accept: "application/json" } });
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.error || `Request failed (${r.status})`);
  return data;
}

// ---- priorities (order only) ----------------------------------------------------------
function renderChips() {
  const box = $("#chips");
  box.replaceChildren(...TOPICS.map((t) => el("button", {
    type: "button", class: "chip", "aria-pressed": String(state.priorities.includes(t)),
    onclick: () => {
      state.priorities = state.priorities.includes(t) ? state.priorities.filter((x) => x !== t) : [...state.priorities, t];
      store.set("sb.priorities", state.priorities);
      renderChips();
      if (state.ballot) renderBallot();
    },
  }, t)));
}
const priorityScore = (m) => (m.topics || []).filter((t) => state.priorities.includes(t)).length;

// ---- ballot ---------------------------------------------------------------------------
async function lookup(address) {
  status("Finding your districts and ballot…");
  try {
    const b = await api(`/api/ballot?address=${encodeURIComponent(address)}`);
    state.ballot = b;
    store.set("sb.ballot", b);              // districts and card list only; the address is not saved
    status("");
    showBallot();
  } catch (e) {
    status(e.message);
  }
}

function coveragePill(name, v) {
  const map = { official: ["ok", "official source"], partial: ["", "partial"], not_mapped: ["warn", "not covered yet"] };
  const [cls, txt] = map[v] || ["", v];
  return el("li", { class: `pill ${cls}` }, `${name}: ${txt}`);
}

function renderBallot() {
  const b = state.ballot;
  const ready = b.measures.filter((m) => m.status === "ready").length + b.races.filter((r) => r.status === "ready").length;
  $("#summary").replaceChildren(
    el("h2", {}, "Your ballot in 60 seconds"),
    el("div", { class: "stats" },
      el("span", {}, el("b", {}, b.measures.length), " measures"),
      el("span", {}, el("b", {}, b.races.length), " races"),
      el("span", {}, el("b", {}, `${b.minutes_to_read} min`), ` to read the ${ready} ready cards`)),
    el("ul", { class: "districts", "aria-label": "Your districts" },
      Object.entries(b.districts).map(([k, v]) => el("li", { class: "pill" }, `${k}: ${v}`))),
    el("ul", { class: "coverage", "aria-label": "Coverage" },
      Object.entries(b.coverage).map(([k, v]) => coveragePill(k, v))),
    b.election_passed ? el("p", { class: "notice" },
      `Look-back: this is the ${b.election} ballot, shown as it stood before the vote. No results are shown.`) : null,
    el("p", { class: "notice" }, b.note, " ", ...b.official_links.flatMap((l) => [extLink(l.url, l.label), " "])),
  );
  const measures = [...b.measures].sort((a, c) => priorityScore(c) - priorityScore(a));
  $("#measures").replaceChildren(...measures.map((m) => el("li", {}, listItem(m))));
  $("#races").replaceChildren(...b.races.map((r) => el("li", {}, raceItem(r))));
}

function listItem(m) {
  if (m.status !== "ready") {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, m.number),
      el("span", { class: "ttl" }, m.official_title), el("span", { class: "meta" }, "Not researched yet"));
  }
  const matched = (m.topics || []).filter((t) => state.priorities.includes(t));
  return el("button", { class: "item", onclick: () => go(m.id) },
    el("span", { class: "num" }, m.number),
    el("span", { class: "ttl" }, m.plain_title),
    el("span", { class: "meta" },
      `${m.reading_minutes} min read`,
      m.verified ? el("span", { class: "pill ok" }, "Both sides checked") : el("span", { class: "pill warn" }, "Steelman unverified"),
      ...matched.map((t) => el("span", { class: "pill" }, t))));
}

function raceItem(r) {
  const label = { ready: null, not_researched: "Not researched yet", check_official_ballot: "May not be on your ballot: check the official sample ballot" }[r.status];
  if (r.status !== "ready" || !r.id) {
    return el("div", { class: "item disabled" }, el("span", { class: "num" }, r.level),
      el("span", { class: "ttl" }, r.office), el("span", { class: "meta" }, label));
  }
  return el("button", { class: "item", onclick: () => go(r.id) },
    el("span", { class: "num" }, r.level), el("span", { class: "ttl" }, r.office),
    el("span", { class: "meta" }, r.candidates.join(" · ")));
}

// ---- routing ---------------------------------------------------------------------------
function go(id) { location.hash = id ? `card=${id}` : ""; }
window.addEventListener("hashchange", route);

async function route() {
  const id = (location.hash.match(/card=([A-Za-z0-9-]+)/) || [])[1];
  if (!id) return showBallot();
  $("#lookup").hidden = true; $("#ballot").hidden = true;
  const box = $("#detail"); box.hidden = false;
  box.replaceChildren(el("p", { class: "status" }, "Loading…"));
  try {
    const rec = await api(`/api/card/${encodeURIComponent(id)}`);
    box.replaceChildren(backButton(), "steelman_yes" in rec.card ? measureCard(rec) : raceCard(rec));
    window.scrollTo(0, 0);
  } catch (e) {
    box.replaceChildren(backButton(), el("p", { class: "status" }, e.message));
  }
}

function showBallot() {
  $("#detail").hidden = true; $("#lookup").hidden = false;
  if (state.ballot) { $("#ballot").hidden = false; renderBallot(); }
}
const backButton = () => el("p", { class: "back" }, el("button", { class: "btn secondary", onclick: () => go(null) }, "← Back to my ballot"));

// ---- measure card ------------------------------------------------------------------------
function claimLi(c) {
  return el("li", {}, el("span", { class: "tag" }, c.label), c.text,
    c.whose ? el("span", { class: "muted" }, ` (${c.whose})`) : null, " ",
    el("span", { class: "src" }, "[", extLink(c.source_url, "source"), "]"));
}

function side(title, s) {
  const more = el("div", { class: "more", hidden: true },
    s.more_reasons.length ? el("ul", {}, s.more_reasons.map((r) => el("li", {}, r))) : null,
    el("p", {}, el("b", {}, "Evidence they point to")),
    el("ul", {}, s.best_evidence.map(claimLi)),
    el("p", {}, el("b", {}, "Who it helps, in their view: "), s.who_it_helps),
    el("p", {}, el("b", {}, "Their answer to the other side: "), s.answer_to_other_side),
    s.values.length ? el("p", { class: "muted" }, "Values: ", s.values.join(", ")) : null);
  const n = s.more_reasons.length;
  const btn = el("button", { class: "toggle", "aria-expanded": "false", onclick: () => {
    more.hidden = !more.hidden; btn.setAttribute("aria-expanded", String(!more.hidden));
    btn.textContent = more.hidden ? `More reasons${n ? ` (${n})` : ""} and evidence` : "Show less";
  } }, `More reasons${n ? ` (${n})` : ""} and evidence`);
  return el("section", { class: "side" }, el("h4", {}, title),
    s.basis === "no_organized_side" ? el("p", { class: "muted" }, "No official argument was submitted for this side; this case comes from the nonpartisan analysis.") : null,
    el("p", { class: "headline" }, s.headline), btn, more);
}

function measureCard(rec) {
  const c = rec.card;
  const yesFirst = (parseInt((c.number.match(/\d+/) || ["0"])[0], 10) % 2) === 1;   // alternate order by number
  const sides = [side("Strongest case for YES", c.steelman_yes), side("Strongest case for NO", c.steelman_no)];
  if (!yesFirst) sides.reverse();
  return el("article", { class: "panel card" },
    el("p", { class: "num" }, c.number),
    el("h1", {}, c.plain_title),
    el("p", { class: "official" }, "Official title: ", c.official_title, c.title_disputed ? " ⚖️ title challenged" : ""),
    el("div", { class: "badges" },
      rec.steelman_verified ? el("span", { class: "pill ok" }, "Both sides checked by our fairness review")
        : el("span", { class: "pill warn" }, "Steelman unverified: our fairness review still had notes"),
      el("span", { class: "pill" }, `${c.reading_minutes} min read`),
      el("span", { class: "pill" }, `Put on ballot by: ${c.put_on_ballot_by}`)),
    el("div", { class: "yesno" },
      el("p", {}, el("b", {}, "A YES vote means: "), c.yes_means),
      el("p", {}, el("b", {}, "A NO vote means: "), c.no_means)),
    el("h3", {}, "What changes"),
    el("div", { class: "changes" }, c.what_changes.map((r) => el("div", { class: "change" },
      el("div", { class: "topic" }, r.topic),
      el("div", { class: "cols" },
        el("div", { class: "col" }, el("span", { class: "lbl" }, "Today"), r.today),
        el("div", { class: "col" }, el("span", { class: "lbl" }, "If it passes"), r.if_passes,
          r.label === "prediction" ? el("span", { class: "muted" }, ` (estimate: ${r.whose || "unattributed"})`) : null,
          " ", el("span", { class: "src" }, "[", extLink(r.source_url, "source"), "]")))))),
    el("h3", {}, "Each side's strongest case"),
    el("div", { class: "sides" }, sides),
    el("p", { class: "crux" }, el("b", {}, `Where they really disagree (${c.crux.kind}): `), c.crux.text),
    el("h3", {}, "What the evidence says"),
    el("ul", { class: "evidence" }, [c.fiscal_impact, ...c.evidence].map(claimLi)),
    el("h3", {}, "Who is affected"),
    el("ul", {}, c.who_is_affected.map((w) => el("li", {}, w))),
    shareBar(c.measure_id),
    el("h3", {}, "Sources"),
    el("ul", { class: "sources" }, (rec.sources || []).map((u) => el("li", {}, extLink(u, u)))),
    el("p", { class: "muted" }, "We never tell you how to vote."));
}

// ---- race card ------------------------------------------------------------------------------
function raceCard(rec) {
  const c = rec.card;
  return el("article", { class: "panel card" },
    el("p", { class: "num" }, "Race"),
    el("h1", {}, c.office),
    el("p", {}, el("b", {}, "What this office does: "), c.what_office_does.text, " ",
      el("span", { class: "src" }, "[", extLink(c.what_office_does.source_url, "source"), "]")),
    el("p", { class: "muted" }, rec.ballot_order_note || "Candidates in official ballot order."),
    el("div", { class: "cands" }, c.candidates.map((p) => el("section", { class: "side cand" },
      el("h4", {}, p.name, " ", el("span", { class: "party" }, `· ${p.party}`)),
      p.says_basis === "none_found"
        ? el("p", {}, "No statement submitted to the official voter guide.")
        : [el("p", { class: "headline" }, p.headline || p.core_case),
           el("p", {}, p.core_case),
           el("ul", {}, p.says.map(claimLi))],
      el("p", { class: "muted" }, "Did: no legislative record in our sources · Funded by: state campaign finance not connected yet")))),
    c.where_they_differ ? el("p", { class: "crux" }, el("b", {}, "Where they differ: "), c.where_they_differ.text) : null,
    el("p", { class: "muted" }, "Statements were written by the candidates and not checked by any official agency. We never tell you how to vote."));
}

// ---- sharing (always both sides) -----------------------------------------------------------
function shareBar(id) {
  const out = el("p", { class: "status", role: "status" });
  const qrBox = el("div", { class: "qr", hidden: true });
  const copy = async (text, msg) => {
    try { await navigator.clipboard.writeText(text); out.textContent = msg; }
    catch { out.textContent = "Copy didn't work here. Press and hold the text to copy it."; }
  };
  const getShare = () => api(`/api/share/${encodeURIComponent(id)}`);
  return el("div", {},
    el("h3", {}, "Share both sides"),
    el("div", { class: "share" },
      el("button", { class: "btn", onclick: async () => { const s = await getShare(); location.href = s.whatsapp_link; } }, "WhatsApp"),
      el("button", { class: "btn", onclick: async () => {
        const s = await getShare(); await copy(s.wechat, "Copied for WeChat: paste it into a chat. Or let a friend scan the QR code.");
        qrBox.replaceChildren(el("img", { src: `/api/qr/${encodeURIComponent(id)}.svg`, alt: "QR code linking to this card" }));
        qrBox.hidden = false;
      } }, "WeChat"),
      navigator.share ? el("button", { class: "btn secondary", onclick: async () => {
        const s = await getShare(); try { await navigator.share({ title: "Steelman Ballot", text: s.plain }); } catch { /* cancelled */ }
      } }, "More…") : null,
      el("button", { class: "btn secondary", onclick: async () => { const s = await getShare(); copy(s.url, "Link copied."); } }, "Copy link")),
    qrBox, out);
}

// ---- start ---------------------------------------------------------------------------------
$("#address-form").addEventListener("submit", (e) => { e.preventDefault(); lookup($("#address").value.trim()); });
$("#example").addEventListener("click", () => { $("#address").value = EXAMPLE; lookup(EXAMPLE); });
renderChips();
route();
if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
