// Anthropic IPO Watch: small enhancements. The page works without this file:
// numbers open their source card through the native popover attribute, and
// every value a chart draws is also in a table.
(() => {
  "use strict";

  const PANELS = {
    m: "market", v: "value", e: "ev", s: "shares", u: "unlock", k: "control",
    c: "contracts", g: "growth", l: "losses", t: "timeline", f: "filings", w: "visits",
    h: "history",
  };
  const canHover = window.matchMedia("(hover: hover) and (pointer: fine)").matches;
  const supportsPopover = "showPopover" in HTMLElement.prototype;
  let invoker = null;
  let hoverTimer = null;
  let hoverOpened = null;

  // -- keyboard: one key per panel ---------------------------------------
  document.addEventListener("keydown", (event) => {
    if (event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    const target = event.target;
    if (target instanceof HTMLElement && target.matches("input, textarea, select, [contenteditable]")) return;
    if (event.key === "?") {
      const help = document.getElementById("help");
      if (help && supportsPopover) help.togglePopover();
      return;
    }
    const id = PANELS[event.key.toLowerCase()];
    if (!id) return;
    const panel = document.getElementById(id);
    if (!panel) return;
    event.preventDefault();
    panel.focus({ preventScroll: true });
    panel.scrollIntoView({ block: "start" });
    history.replaceState(null, "", "#" + id);
  });

  // -- overview: days until the reported pricing date ---------------------------
  // Shown only by the reader's browser, from the date on the page: the page itself is
  // cached on the server and could not count days.
  document.querySelectorAll("[data-until]").forEach((el) => {
    const until = el.getAttribute("data-until");
    if (!/^\d{4}-\d{2}-\d{2}$/.test(until)) return;
    const now = new Date().toLocaleDateString("en-CA", { timeZone: "America/New_York" });
    const days = Math.round((Date.parse(until) - Date.parse(now)) / 86400000);
    if (days < 0) return;
    el.textContent = days === 0 ? "· pricing today" : days === 1 ? "· pricing tomorrow" : `· pricing in ${days} days`;
    el.hidden = false;
  });

  // -- visits: count this session once, then show the counts and their line ------
  // Nothing about the reader is sent or kept: the service adds one to the count of the
  // day and of the hour. The line is drawn here because the page is cached on the server.
  const SVG = "http://www.w3.org/2000/svg";
  function el(name, attrs, text) {
    const node = document.createElementNS(SVG, name);
    Object.entries(attrs).forEach(([key, value]) => node.setAttribute(key, String(value)));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function drawVisits(points, label) {
    const W = 320, H = 132, left = 30, right = 10, top = 12, bottom = 24;
    const top_value = Math.max(1, ...points.map((p) => p.value));
    const step = top_value <= 4 ? 1 : Math.ceil(top_value / 4);
    const high = Math.ceil(top_value / step) * step;
    const x = (i) => left + (points.length === 1 ? (W - left - right) / 2 : (i * (W - left - right)) / (points.length - 1));
    const y = (v) => H - bottom - (v / high) * (H - top - bottom);
    const svg = el("svg", { class: "chart-svg", viewBox: `0 0 ${W} ${H}`, role: "img", "aria-label": label });
    const axis = el("g", { class: "axis", "aria-hidden": "true" });
    for (let v = 0; v <= high; v += step) {
      axis.append(el("line", { class: v === 0 ? "zero" : "grid", x1: left, x2: W - right, y1: y(v), y2: y(v) }));
      axis.append(el("text", { class: "tick", x: left - 6, y: y(v) + 3.5, "text-anchor": "end" }, String(v)));
    }
    const first = points[0].name, last = points[points.length - 1].name;
    axis.append(el("text", { class: "xl", x: left, y: H - 6, "text-anchor": "start" }, first));
    if (points.length > 1) axis.append(el("text", { class: "xl", x: W - right, y: H - 6, "text-anchor": "end" }, last));
    svg.append(axis);
    const path = points.map((p, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(p.value).toFixed(1)}`).join(" ");
    svg.append(el("path", { class: "ln s1", d: path }));
    const end = points[points.length - 1];
    svg.append(el("circle", { class: "dot s1", cx: x(points.length - 1), cy: y(end.value), r: 3 }));
    return svg;
  }
  (async () => {
    const box = document.getElementById("visits");
    if (!box || !window.fetch) return;
    try {
      let counted = false;
      try { counted = sessionStorage.getItem("ipo-seen") === "1"; } catch (e) { /* private mode */ }
      if (!counted) {
        await fetch("/seen", { method: "POST", keepalive: true });
        try { sessionStorage.setItem("ipo-seen", "1"); } catch (e) { /* private mode */ }
      }
      const stats = await (await fetch("/stats", { cache: "no-store" })).json();
      const month = (iso) => new Date(iso.slice(0, 10) + "T12:00:00Z").toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
      box.querySelector(".v-today").textContent = Number(stats.today).toLocaleString("en-US");
      box.querySelector(".v-total").textContent = Number(stats.total).toLocaleString("en-US");
      box.querySelector(".v-since").textContent = month(stats.since);
      box.querySelector(".v-numbers").hidden = false;
      // A line per day once there are a few days; before that, per hour.
      const byDay = stats.days.length >= 3;
      const points = byDay
        ? stats.days.map((d) => ({ name: month(d.day), value: d.visits }))
        : stats.hours.map((h) => ({ name: `${month(h.hour)} ${Number(h.hour.slice(11))}h`, value: h.visits }));
      if (points.length) {
        const caption = byDay ? "Visits per day, New York time" : "Visits per hour, New York time";
        box.querySelector(".v-caption").textContent = caption;
        box.querySelector(".v-plot").replaceChildren(drawVisits(points, caption));
        box.querySelector(".v-chart").hidden = false;
      }
    } catch (e) {
      /* the counts are a nicety: the page works without them */
    }
  })();

  // -- phone: the tables behind the charts start folded ------------------------
  if (window.matchMedia("(max-width: 640px)").matches) {
    document.querySelectorAll("details.fold").forEach((fold) => fold.removeAttribute("open"));
  }

  // -- the tables behind the charts, opened or folded together --------------------
  const foldAll = document.querySelector(".fold-all");
  if (foldAll) {
    foldAll.hidden = false;
    foldAll.addEventListener("click", (event) => {
      const button = event.target instanceof Element ? event.target.closest("[data-folds]") : null;
      if (!button) return;
      const open = button.getAttribute("data-folds") === "open";
      document.querySelectorAll("details.fold").forEach((fold) => {
        fold.open = open;
      });
    });
  }

  // -- panel bar: show where the reader is ------------------------------------
  const links = new Map();
  document.querySelectorAll('.keys a[href^="#"]').forEach((link) => {
    links.set(link.getAttribute("href").slice(1), link);
  });
  if ("IntersectionObserver" in window && links.size) {
    const visible = new Set();
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) visible.add(entry.target.id);
          else visible.delete(entry.target.id);
        });
        // The first panel in page order that crosses the reading line.
        let current = null;
        links.forEach((link, id) => {
          if (!current && visible.has(id)) current = id;
        });
        links.forEach((link, id) => {
          if (id === current) link.setAttribute("aria-current", "true");
          else link.removeAttribute("aria-current");
        });
      },
      { rootMargin: "-30% 0px -65% 0px" },
    );
    links.forEach((link, id) => {
      const panel = document.getElementById(id);
      if (panel) observer.observe(panel);
    });
  }

  // -- market: say when the page has newer figures, never reload by surprise --------
  const fresh = document.getElementById("fresh");
  if (fresh && document.body.dataset.market !== "off" && "fetch" in window) {
    let seen = null;
    const look = () => {
      if (document.visibilityState !== "visible") return;
      fetch("/", { method: "HEAD", cache: "no-store" })
        .then((response) => {
          const tag = response.headers.get("ETag");
          if (!tag) return;
          if (seen === null) seen = tag;
          else if (tag !== seen) fresh.hidden = false;
        })
        .catch(() => {});
    };
    fresh.addEventListener("click", () => window.location.reload());
    look();
    window.setInterval(look, 60000);
  }

  if (!supportsPopover) return;

  // -- source cards: place them next to the number -------------------------
  function place(card, anchor) {
    const gap = 8;
    const rect = anchor.getBoundingClientRect();
    card.classList.add("placed");
    card.style.position = "fixed";
    card.style.left = "0px";
    card.style.top = "0px";
    const width = card.offsetWidth;
    const height = card.offsetHeight;
    let left = Math.min(Math.max(gap, rect.left), window.innerWidth - width - gap);
    let top = rect.bottom + gap;
    if (top + height > window.innerHeight - gap) {
      const above = rect.top - gap - height;
      top = above >= gap ? above : Math.max(gap, window.innerHeight - height - gap);
    }
    card.style.left = Math.round(left) + "px";
    card.style.top = Math.round(top) + "px";
  }

  function cardOf(button) {
    const id = button.getAttribute("popovertarget");
    return id ? document.getElementById(id) : null;
  }

  document.addEventListener(
    "click",
    (event) => {
      const button = event.target instanceof Element ? event.target.closest("button[popovertarget]") : null;
      if (button) {
        invoker = button;
        hoverOpened = null;
      }
    },
    true,
  );

  document.addEventListener(
    "toggle",
    (event) => {
      const card = event.target;
      if (!(card instanceof HTMLElement) || !card.matches("[popover]")) return;
      const open = event.newState === "open";
      document.querySelectorAll('button[popovertarget="' + card.id + '"]').forEach((button) => {
        button.setAttribute("aria-expanded", String(open && button === invoker));
      });
      if (open && invoker && window.innerWidth > 640) place(card, invoker);
      if (!open && hoverOpened === card) hoverOpened = null;
    },
    true,
  );

  // -- charts: a mark opens the same source card as its number -------------
  const tip = document.getElementById("tip");
  const sourced = (target) => (target instanceof Element ? target.closest(".chart-svg [data-src]") : null);
  let pressed = null;

  function openSource(mark) {
    const card = document.getElementById(mark.getAttribute("data-src"));
    if (!card) return;
    hideTip();
    invoker = mark;
    hoverOpened = null;
    if (!card.matches(":popover-open")) card.showPopover();
  }

  function showTip(mark) {
    const text = mark.getAttribute("data-tip");
    if (!tip || !text) return;
    const shape = mark.querySelector(".col, .dot, .pointer") || mark;
    const rect = shape.getBoundingClientRect();
    tip.textContent = text;
    tip.hidden = false;
    const width = tip.offsetWidth;
    const left = Math.min(Math.max(8, rect.left + rect.width / 2 - width / 2), window.innerWidth - width - 8);
    const above = rect.top - tip.offsetHeight - 8;
    tip.style.left = Math.round(left) + "px";
    tip.style.top = Math.round(above >= 8 ? above : rect.bottom + 8) + "px";
  }

  function hideTip() {
    if (tip) tip.hidden = true;
  }

  // A press on a mark whose card is open closes it; the click must not reopen it.
  document.addEventListener(
    "pointerdown",
    (event) => {
      const mark = sourced(event.target);
      const card = mark ? document.getElementById(mark.getAttribute("data-src")) : null;
      pressed = card && card.matches(":popover-open") ? mark : null;
    },
    true,
  );

  document.addEventListener("click", (event) => {
    const mark = sourced(event.target);
    if (!mark) return;
    if (pressed === mark) {
      pressed = null;
      return;
    }
    openSource(mark);
  });

  // One tab stop per chart; the arrow keys move between its marks.
  document.querySelectorAll(".chart-svg").forEach((chart) => {
    const marks = Array.from(chart.querySelectorAll(".mark"));
    if (!marks.length) return;
    chart.setAttribute("role", "group");
    marks.forEach((mark, index) => {
      mark.setAttribute("role", "button");
      mark.setAttribute("tabindex", index === 0 ? "0" : "-1");
      mark.setAttribute(
        "aria-label",
        mark.getAttribute("data-tip") + " (" + mark.getAttribute("data-kind") + ", show source)",
      );
      mark.addEventListener("focus", () => showTip(mark));
      mark.addEventListener("blur", hideTip);
      mark.addEventListener("keydown", (event) => {
        let next = null;
        if (event.key === "ArrowRight" || event.key === "ArrowDown") next = marks[index + 1];
        else if (event.key === "ArrowLeft" || event.key === "ArrowUp") next = marks[index - 1];
        else if (event.key === "Home") next = marks[0];
        else if (event.key === "End") next = marks[marks.length - 1];
        else if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          openSource(mark);
          return;
        } else return;
        event.preventDefault();
        if (!next) return;
        mark.setAttribute("tabindex", "-1");
        next.setAttribute("tabindex", "0");
        next.focus();
      });
    });
  });

  if (canHover) {
    document.addEventListener("mouseover", (event) => {
      const mark = event.target instanceof Element ? event.target.closest(".chart-svg .mark") : null;
      if (mark) showTip(mark);
    });
    document.addEventListener("mouseout", (event) => {
      const mark = event.target instanceof Element ? event.target.closest(".chart-svg .mark") : null;
      const to = event.relatedTarget instanceof Element ? event.relatedTarget.closest(".chart-svg .mark") : null;
      if (mark && mark !== to) hideTip();
    });
    window.addEventListener("scroll", hideTip, { passive: true });
  }

  // -- hover (desktop only): open after a short pause ----------------------
  if (canHover) {
    const close = () => {
      clearTimeout(hoverTimer);
      if (hoverOpened && hoverOpened.matches(":popover-open")) hoverOpened.hidePopover();
      hoverOpened = null;
    };

    document.addEventListener("mouseover", (event) => {
      const button = event.target instanceof Element ? event.target.closest("button.n") : null;
      if (!button) return;
      clearTimeout(hoverTimer);
      hoverTimer = setTimeout(() => {
        const card = cardOf(button);
        if (!card || card.matches(":popover-open")) return;
        if (document.querySelector("[popover]:popover-open") && !hoverOpened) return;
        invoker = button;
        card.showPopover();
        hoverOpened = card;
      }, 320);
    });

    document.addEventListener("mouseout", (event) => {
      const from = event.target instanceof Element ? event.target.closest("button.n, [popover]") : null;
      if (!from) return;
      const to = event.relatedTarget instanceof Element ? event.relatedTarget.closest("button.n, [popover]") : null;
      if (to && (to === hoverOpened || to === invoker)) return;
      clearTimeout(hoverTimer);
      if (hoverOpened) hoverTimer = setTimeout(close, 180);
    });

    document.addEventListener("mouseover", (event) => {
      const over = event.target instanceof Element ? event.target.closest("[popover]") : null;
      if (over && over === hoverOpened) clearTimeout(hoverTimer);
    });
  }
})();
