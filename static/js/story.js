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

if (root) {
  const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const saveData = !!(navigator.connection && navigator.connection.saveData);
  const host = root.querySelector("[data-story-stage]");

  if (!host || reduceMotion || saveData || !webglAvailable()) {
    root.classList.add("story-static");
  } else {
    const sceneUrl = root.getAttribute("data-story-src");
    const load = () =>
      import(sceneUrl)
        .then((m) => m.start(root, host))
        .catch(() => root.classList.add("story-static"));
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
