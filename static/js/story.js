// CampusHub scroll story loader (tiny). The 3D scene (static/js/story-scene.js,
// built from assets/story/scene.js) is only downloaded when a story section is
// about to scroll into view, and never when the visitor:
//   - prefers reduced motion,
//   - has data saver on, or
//   - has a browser/device without WebGL.
// In those cases the story stays a simple, fast list of chapters.
const root = document.querySelector("[data-story]");

function webglAvailable() {
  try {
    const c = document.createElement("canvas");
    return !!(window.WebGLRenderingContext && (c.getContext("webgl2") || c.getContext("webgl")));
  } catch {
    return false;
  }
}

// Show the simple list, and say why the 3D view is off so it's easy to fix.
function staticMode(root, reason) {
  root.classList.add("story-static");
  const note = root.querySelector("[data-story-note]");
  if (note && reason) {
    note.textContent = "3D view is off: " + reason;
    note.hidden = false;
  }
}

if (root) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData = !!(navigator.connection && navigator.connection.saveData);
  const host = root.querySelector("[data-story-stage]");

  if (!host) {
    staticMode(root);
  } else if (reduceMotion) {
    staticMode(root, "your device asks for reduced motion (Windows: Settings › Accessibility › Visual effects › Animation effects).");
  } else if (saveData) {
    staticMode(root, "your browser's data saver is on.");
  } else if (!webglAvailable()) {
    staticMode(root, "your browser has WebGL turned off (check that hardware acceleration is on in the browser settings).");
  } else {
    const sceneUrl = root.getAttribute("data-story-src");
    const load = () =>
      import(sceneUrl)
        .then((m) => m.start(root, host))
        .catch((e) => {
          console.error("CampusHub 3D story failed to load", e);
          staticMode(root, "the 3D file couldn't load. Run `npm run story`, then refresh.");
        });
    const io = new IntersectionObserver(
      (entries) => {
        if (entries.some((e) => e.isIntersecting)) {
          io.disconnect();
          load();
        }
      },
      { rootMargin: "800px 0px" },
    );
    io.observe(root);
  }
}
