(() => {
  const root = document.documentElement;
  const toggle = document.querySelector("[data-theme-toggle]");
  const label = document.querySelector("[data-theme-label]");
  const key = "goreecloud-manager-theme";
  const modes = ["system", "light", "dark"];

  function readPreference() {
    try {
      const value = window.localStorage.getItem(key);
      return modes.includes(value) ? value : "system";
    } catch {
      return "system";
    }
  }

  function savePreference(value) {
    try {
      if (value === "system") {
        window.localStorage.removeItem(key);
      } else {
        window.localStorage.setItem(key, value);
      }
    } catch {
      // Keep the in-memory selection if browser storage is unavailable.
    }
  }

  function apply(value) {
    if (value === "system") {
      root.removeAttribute("data-theme");
    } else {
      root.setAttribute("data-theme", value);
    }

    if (label) {
      label.textContent = value[0].toUpperCase() + value.slice(1);
    }

    if (toggle) {
      toggle.setAttribute("aria-label", `Appearance: ${value}. Activate to change theme.`);
    }
  }

  let current = readPreference();
  apply(current);

  if (toggle) {
    toggle.addEventListener("click", () => {
      const index = modes.indexOf(current);
      current = modes[(index + 1) % modes.length];
      savePreference(current);
      apply(current);
    });
  }
})();
