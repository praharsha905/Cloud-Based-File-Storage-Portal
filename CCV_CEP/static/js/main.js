(function () {
  function setupAnimatedSections() {
    const animated = document.querySelectorAll("[data-animate]");
    if (!animated.length) {
      return;
    }

    animated.forEach((item) => {
      const delay = Number(item.getAttribute("data-delay") || 0);
      item.style.setProperty("--delay", `${delay}ms`);
    });

    if (!("IntersectionObserver" in window)) {
      animated.forEach((item) => item.classList.add("in-view"));
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (entry.isIntersecting) {
            entry.target.classList.add("in-view");
            observer.unobserve(entry.target);
          }
        });
      },
      { threshold: 0.12 }
    );

    animated.forEach((item) => observer.observe(item));
  }

  function setupProgressBars() {
    const bars = document.querySelectorAll("[data-progress]");
    bars.forEach((bar) => {
      const value = Number(bar.getAttribute("data-progress") || 0);
      const safeValue = Math.max(0, Math.min(100, value));
      requestAnimationFrame(() => {
        bar.style.width = `${safeValue}%`;
      });
    });
  }

  function setupCopyButtons() {
    const copyButtons = document.querySelectorAll("[data-copy-text]");
    copyButtons.forEach((button) => {
      button.addEventListener("click", async () => {
        const text = button.getAttribute("data-copy-text");
        if (!text) {
          return;
        }

        const originalLabel = button.textContent;
        try {
          await navigator.clipboard.writeText(text);
          button.textContent = "Copied";
        } catch (error) {
          button.textContent = "Failed";
        }

        window.setTimeout(() => {
          button.textContent = originalLabel;
        }, 1300);
      });
    });
  }

  function setupPasswordToggles() {
    const toggles = document.querySelectorAll("[data-toggle-password]");
    toggles.forEach((toggle) => {
      toggle.addEventListener("click", () => {
        const targetId = toggle.getAttribute("data-toggle-password");
        if (!targetId) {
          return;
        }

        const input = document.getElementById(targetId);
        if (!input) {
          return;
        }

        const isPassword = input.type === "password";
        input.type = isPassword ? "text" : "password";
        toggle.textContent = isPassword ? "Hide" : "Show";
      });
    });
  }

  function setupFileInputLabels() {
    const inputs = document.querySelectorAll("[data-file-input]");
    inputs.forEach((input) => {
      input.addEventListener("change", () => {
        const targetId = input.getAttribute("data-file-target");
        if (!targetId) {
          return;
        }

        const label = document.getElementById(targetId);
        if (!label) {
          return;
        }

        const fileName = input.files && input.files[0] ? input.files[0].name : "No file selected.";
        label.textContent = fileName;
      });
    });
  }

  function setupImpressTip() {
    const tipNode = document.querySelector("[data-rotating-tip]");
    if (!tipNode) {
      return;
    }

    const tips = [
      "Zero-clutter workflow with one dashboard for every action.",
      "Timed links let you share confidently and revoke by expiry.",
      "Professional UI tuned for smooth mobile and desktop demos.",
      "Interactive storage indicators make usage instantly clear.",
    ];

    let current = 0;
    tipNode.textContent = tips[current];

    window.setInterval(() => {
      current = (current + 1) % tips.length;
      tipNode.classList.remove("flash");
      void tipNode.offsetWidth;
      tipNode.classList.add("flash");
      tipNode.textContent = tips[current];
    }, 3200);
  }

  function setupLiveClock() {
    const timeNode = document.querySelector("[data-live-time]");
    if (!timeNode) {
      return;
    }

    const update = () => {
      const now = new Date();
      const time = now.toISOString().slice(11, 19);
      timeNode.textContent = time;
    };

    update();
    window.setInterval(update, 1000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupAnimatedSections();
    setupProgressBars();
    setupCopyButtons();
    setupPasswordToggles();
    setupFileInputLabels();
    setupImpressTip();
    setupLiveClock();
  });
})();
