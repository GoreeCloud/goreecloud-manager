(() => {
  "use strict";

  const root = document.documentElement;
  const storageKey = "goreecloud-manager-theme";
  const modes = ["system", "light", "dark"];

  function readPreference() {
    try {
      const value = window.localStorage.getItem(storageKey);
      return modes.includes(value) ? value : "system";
    } catch {
      return "system";
    }
  }

  function savePreference(value) {
    try {
      if (value === "system") {
        window.localStorage.removeItem(storageKey);
      } else {
        window.localStorage.setItem(storageKey, value);
      }
    } catch {
      // Browser storage is optional. Keep the current in-memory selection instead.
    }
  }

  function applyRootAppearance(value) {
    if (value === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", value);
    }
    root.dataset.appearance = value;
  }

  let current = readPreference();

  // This script intentionally runs before the stylesheet so an explicit local
  // preference is applied before first paint. It never sends the preference to
  // Manager or any external service.
  applyRootAppearance(current);

  function bindAppearanceControl() {
    const toggle = document.querySelector("[data-theme-toggle]");
    const label = document.querySelector("[data-theme-label]");

    function updateControl() {
      if (label) {
        label.textContent = current[0].toUpperCase() + current.slice(1);
      }
      if (toggle) {
        toggle.setAttribute(
          "aria-label",
          `Appearance: ${current}. Activate to change theme.`,
        );
      }
    }

    updateControl();

    if (!toggle) {
      return;
    }

    toggle.addEventListener("click", () => {
      const index = modes.indexOf(current);
      current = modes[(index + 1) % modes.length];
      savePreference(current);
      applyRootAppearance(current);
      updateControl();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindAppearanceControl, { once: true });
  } else {
    bindAppearanceControl();
  }
})();
