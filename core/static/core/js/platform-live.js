(() => {
  "use strict";

  if (typeof window.EventSource !== "function") {
    return;
  }

  const pageUrl = new URL(window.location.href);
  if (!pageUrl.pathname.endsWith("/platform/")) {
    return;
  }

  const streamUrl = new URL("events/", pageUrl);
  if (streamUrl.origin !== pageUrl.origin) {
    return;
  }

  let reloadScheduled = false;
  const stream = new window.EventSource(streamUrl.pathname);

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
