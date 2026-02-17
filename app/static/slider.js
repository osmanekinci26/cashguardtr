(function () {
  const slider = document.querySelector("[data-slider]");
  if (!slider) return;

  const slidesEl = slider.querySelector("[data-slides]");
  const slides = Array.from(slider.querySelectorAll(".slide"));
  const prevBtn = slider.querySelector("[data-prev]");
  const nextBtn = slider.querySelector("[data-next]");
  const dotsEl = slider.querySelector("[data-dots]");

  let idx = 0;
  let timer = null;

  function go(i) {
    idx = (i + slides.length) % slides.length;
    slidesEl.style.transform = `translateX(-${idx * 100}%)`;
    if (dotsEl) {
      dotsEl.querySelectorAll("button").forEach((b, bi) => {
        b.classList.toggle("active", bi === idx);
      });
    }
  }

  function buildDots() {
    if (!dotsEl) return;
    dotsEl.innerHTML = "";
    slides.forEach((_, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.setAttribute("aria-label", `Görsel ${i + 1}`);
      b.addEventListener("click", () => {
        stop();
        go(i);
        start();
      });
      dotsEl.appendChild(b);
    });
  }

  function start() {
    stop();
    timer = setInterval(() => go(idx + 1), 4500);
  }

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }

  buildDots();
  go(0);
  start();

  prevBtn?.addEventListener("click", () => { stop(); go(idx - 1); start(); });
  nextBtn?.addEventListener("click", () => { stop(); go(idx + 1); start(); });

  // hover/touch pause
  slider.addEventListener("mouseenter", stop);
  slider.addEventListener("mouseleave", start);
})();


