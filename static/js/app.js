// CampusHub progressive enhancement. Every page works without this file.
(function () {
  "use strict";
  var $$ = function (sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); };

  document.addEventListener("click", function (e) {
    // Dialogs: <button data-dialog-open="id"> opens <dialog id="id">; [data-dialog-close] closes.
    var open = e.target.closest("[data-dialog-open]");
    if (open) {
      var d = document.getElementById(open.getAttribute("data-dialog-open"));
      if (d && d.showModal) { d.showModal(); }
      return;
    }
    var close = e.target.closest("[data-dialog-close]");
    if (close) { var dlg = close.closest("dialog"); if (dlg) dlg.close(); }
    // Fill a textarea with a suggested message.
    var fill = e.target.closest("[data-fill]");
    if (fill) {
      var t = document.getElementById(fill.getAttribute("data-fill-target"));
      if (t) { t.value = fill.getAttribute("data-fill"); t.focus(); }
    }
    // Remove an existing photo (its hidden "keep" input goes with it).
    var rm = e.target.closest("[data-remove]");
    if (rm) { var box = rm.closest("[data-photo]"); if (box) box.remove(); }
    // Copy to clipboard.
    var cp = e.target.closest("[data-copy]");
    if (cp && navigator.clipboard) {
      navigator.clipboard.writeText(cp.getAttribute("data-copy")).then(function () {
        var old = cp.textContent; cp.textContent = "Copied ✓"; setTimeout(function () { cp.textContent = old; }, 1500);
      });
    }
  });

  // Auto-submitting selects (campus switcher, sort).
  document.addEventListener("change", function (e) {
    if (e.target.matches("[data-autosubmit]")) { e.target.form.requestSubmit ? e.target.form.requestSubmit() : e.target.form.submit(); }
  });

  // Prevent double submits and show progress.
  document.addEventListener("submit", function (e) {
    var form = e.target;
    if (form.dataset.submitting) { e.preventDefault(); return; }
    form.dataset.submitting = "1";
    $$("button[type=submit]", form).forEach(function (b) {
      b.setAttribute("aria-busy", "true");
      if (b.dataset.pending) { b.textContent = b.dataset.pending; }
      setTimeout(function () { b.disabled = true; }, 0);
    });
  });

  // Chat: Enter sends, Shift+Enter adds a new line.
  document.addEventListener("keydown", function (e) {
    if (e.key === "Enter" && !e.shiftKey && e.target.matches("[data-enter-submit]")) {
      e.preventDefault();
      if (e.target.value.trim()) { e.target.form.requestSubmit(); }
    }
  });

  // Photo picker previews with client-side checks (the server re-validates everything).
  $$("input[type=file][data-preview]").forEach(function (input) {
    var grid = document.getElementById(input.getAttribute("data-preview"));
    var note = document.getElementById(input.getAttribute("data-note"));
    var max = parseInt(input.getAttribute("data-max") || "6", 10);
    input.addEventListener("change", function () {
      $$("[data-new]", grid).forEach(function (n) { n.remove(); });
      var kept = $$("[data-photo]", grid).length;
      var files = Array.prototype.slice.call(input.files);
      var bad = files.filter(function (f) { return !/^image\/(jpeg|png|webp)$/.test(f.type) || f.size > 6 * 1024 * 1024; });
      var msg = "";
      if (bad.length) msg = "Use JPG, PNG or WebP photos under 6 MB.";
      if (files.length + kept > max) msg = "You can add up to " + max + " photos in total.";
      if (note) { note.textContent = msg || note.getAttribute("data-default"); note.classList.toggle("text-danger", !!msg); }
      files.slice(0, Math.max(0, max - kept)).forEach(function (f) {
        var div = document.createElement("div");
        div.setAttribute("data-new", "");
        div.className = "relative aspect-square overflow-hidden rounded-xl border border-line bg-canvas";
        var img = document.createElement("img");
        img.src = URL.createObjectURL(f); img.alt = ""; img.className = "size-full object-cover";
        div.appendChild(img);
        grid.appendChild(div);
      });
    });
  });

  // ---------------------------------------------------------------- 3D effects
  // Pure decoration: pages look and work the same without it.
  var reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var finePointer = window.matchMedia("(hover: hover) and (pointer: fine)").matches;

  // Tilt: [data-tilt] cards lean towards the mouse, with a light glare.
  if (!reduceMotion && finePointer) {
    var active = null, frame = 0, lastEvent = null;
    var MAX = 7; // degrees
    var paint = function () {
      frame = 0;
      if (!active || !lastEvent) return;
      var r = active.getBoundingClientRect();
      var x = (lastEvent.clientX - r.left) / r.width;  // 0..1
      var y = (lastEvent.clientY - r.top) / r.height;  // 0..1
      // Big cards tilt less so text stays easy to read.
      var k = Math.min(1, 320 / Math.max(r.width, r.height));
      active.style.setProperty("--ry", ((x - 0.5) * 2 * MAX * k).toFixed(2) + "deg");
      active.style.setProperty("--rx", ((0.5 - y) * 2 * MAX * k).toFixed(2) + "deg");
      active.style.setProperty("--gx", (x * 100).toFixed(1) + "%");
      active.style.setProperty("--gy", (y * 100).toFixed(1) + "%");
    };
    var reset = function (el) {
      el.classList.remove("is-tilting");
      el.style.setProperty("--rx", "0deg");
      el.style.setProperty("--ry", "0deg");
    };
    document.addEventListener("pointermove", function (e) {
      if (e.pointerType !== "mouse") return;
      var el = e.target.closest ? e.target.closest("[data-tilt]") : null;
      if (el !== active) {
        if (active) reset(active);
        active = el;
        if (active) active.classList.add("is-tilting");
      }
      lastEvent = e;
      if (active && !frame) frame = requestAnimationFrame(paint);
    }, { passive: true });
    document.addEventListener("pointerleave", function () { if (active) { reset(active); active = null; } });
  }

  // Reveal: cards and sections below the fold rise in with a slight 3D turn.
  // Only things not yet on screen are hidden, so nothing flickers on load.
  if (!reduceMotion && "IntersectionObserver" in window) {
    var targets = $$("main [data-tilt], main .card, main section > h2, main .reveal-me").filter(function (el) {
      return !el.closest("[data-story]") && !el.closest("dialog") && el.getBoundingClientRect().top > window.innerHeight;
    });
    var io = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) {
        if (!en.isIntersecting) return;
        en.target.classList.add("is-in");
        io.unobserve(en.target);
        // Hand the transform back to hover/tilt once the entrance is done.
        setTimeout(function () { en.target.classList.remove("reveal", "is-in"); en.target.style.removeProperty("--delay"); }, 1300);
      });
    }, { rootMargin: "0px 0px -8% 0px" });
    targets.forEach(function (el) {
      var i = el.parentElement ? Array.prototype.indexOf.call(el.parentElement.children, el) : 0;
      el.style.setProperty("--delay", (i % 4) * 80 + "ms");
      el.classList.add("reveal");
      io.observe(el);
    });
  }
})();
