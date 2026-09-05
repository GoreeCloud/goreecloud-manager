(() => {
  "use strict";

  const root = document.querySelector("[data-mesh-events-url]");
  if (!root || typeof window.EventSource !== "function") {
    return;
  }

  const url = root.getAttribute("data-mesh-events-url");
  if (!url || !url.startsWith("/")) {
    return;
  }

  let reloadScheduled = false;
  const stream = new window.EventSource(url);

  stream.addEventListener("platform-update", () => {
    if (reloadScheduled) {
      return;
    }
    reloadScheduled = true;
    stream.close();
    window.setTimeout(() => window.location.reload(), 200);
  });

  window.addEventListener(
    "pagehide",
    () => {
      stream.close();
    },
    { once: true },
  );
})();
