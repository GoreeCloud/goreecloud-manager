(() => {
  "use strict";

  const root = document.documentElement;
  const storageKey = "goreecloud-manager-theme";
  const modes = ["system", "light", "dark", "deep-dark"];
  const labels = {
    system: "System",
    light: "Light",
    dark: "Dark",
    "deep-dark": "Deep Dark",
  };

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
      root.removeAttribute("data-glz-appearance");
      root.removeAttribute("data-theme");
      return;
    }

    root.setAttribute("data-glz-appearance", value);
    // Manager's existing product palette still consumes data-theme. Keep this
    // compatibility attribute local while V1.1 data-glz-appearance is the
    // canonical appearance contract.
    root.setAttribute("data-theme", value === "deep-dark" ? "dark" : value);
  }

  let current = readPreference();

  // This script intentionally runs before the stylesheets so an explicit local
  // preference is applied before first paint. It never sends the preference to
  // Manager or any external service.
  applyRootAppearance(current);

  function bindAppearanceControl() {
    const toggle = document.querySelector("[data-theme-toggle]");
    const label = document.querySelector("[data-theme-label]");

    function updateControl() {
      if (label) {
        label.textContent = labels[current];
      }
      if (toggle) {
        toggle.setAttribute(
          "aria-label",
          `Appearance: ${labels[current]}. Activate to change theme.`,
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
