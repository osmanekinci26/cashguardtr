(function () {
  function initSlider(root) {
    const slidesWrap = root.querySelector("[data-slides]");
    if (!slidesWrap) return;

    const slides = Array.from(slidesWrap.children);
    if (!slides.length) return;

    const btnPrev = root.querySelector("[data-prev]");
    const btnNext = root.querySelector("[data-next]");
    const dotsWrap = root.querySelector("[data-dots]");

    let index = 0;
    let timer = null;

    function setX() {
      slidesWrap.style.transform = `translateX(${-index * 100}%)`;
    }

    function renderDots() {
      if (!dotsWrap) return;
      dotsWrap.innerHTML = "";
      slides.forEach((_, i) => {
        const b = document.createElement("button");
        b.type = "button";
        b.className = "dot" + (i === index ? " active" : "");
        b.setAttribute("aria-label", `${i + 1}. görsel`);
        b.addEventListener("click", () => {
          go(i);
          restart();
        });
        dotsWrap.appendChild(b);
      });
    }

    function go(i) {
      index = (i + slides.length) % slides.length;
      setX();
      renderDots();
    }

    function stop() {
      if (timer) clearInterval(timer);
      timer = null;
    }

    function start() {
      stop();
      timer = setInterval(() => go(index + 1), 3500);
    }

    function restart() {
      start();
    }

    if (btnPrev) btnPrev.addEventListener("click", () => { go(index - 1); restart(); });
    if (btnNext) btnNext.addEventListener("click", () => { go(index + 1); restart(); });

    // hover pause
    root.addEventListener("mouseenter", stop);
    root.addEventListener("mouseleave", start);

    // swipe (mobile)
    let x0 = null;
    root.addEventListener("touchstart", (e) => { x0 = e.touches[0].clientX; }, { passive: true });
    root.addEventListener("touchend", (e) => {
      if (x0 === null) return;
      const x1 = e.changedTouches[0].clientX;
      const dx = x1 - x0;
      x0 = null;
      if (Math.abs(dx) < 35) return;
      if (dx > 0) go(index - 1);
      else go(index + 1);
      restart();
    }, { passive: true });

    // init
    go(0);
    start();
  }

  function boot() {
    const sliders = document.querySelectorAll("[data-slider]");
    if (!sliders.length) return;
    sliders.forEach(initSlider);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
