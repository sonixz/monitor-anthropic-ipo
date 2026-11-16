// ANT IPO Monitor: small enhancements. The page works without this file:
// numbers open their source card through the native popover attribute.
(() => {
  "use strict";

  const PANELS = { v: "value", e: "ev", c: "contracts", g: "growth", l: "losses" };
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
