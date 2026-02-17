(() => {
  const slider =
    document.querySelector("[data-slider]") ||
    document.querySelector(".hero-slider") ||
    document.getElementById("heroSlider");

  if (!slider) return;

  const track =
    slider.querySelector(".hs-track") ||
    slider.querySelector("[data-slides]") ||
    slider.querySelector(".slides") ||
    slider.querySelector("#hsTrack");

  if (!track) return;

  // img'ler veya .slide'lar
  const slides = Array.from(track.querySelectorAll("img, .slide"));
  if (!slides.length) return;

  const prevBtn =
    slider.querySelector("[data-prev]") ||
    slider.querySelector(".hs-btn.prev") ||
    slider.querySelector(".slider-btn.prev") ||
    slider.querySelector("#hsPrev");

  const nextBtn =
    slider.querySelector("[data-next]") ||
    slider.querySelector(".hs-btn.next") ||
    slider.querySelector(".slider-btn.next") ||
    slider.querySelector("#hsNext");

  const dotsWrap =
    slider.querySelector("[data-dots]") ||
    slider.querySelector(".hs-dots") ||
    slider.querySelector(".dots") ||
    slider.querySelector("#hsDots");

  const viewport =
    slider.querySelector(".hs-viewport") ||
    slider.querySelector("[data-viewport]") ||
    slider; // fallback

  let index = 0;

  // dots
  let dots = [];
  if (dotsWrap) {
    dotsWrap.innerHTML = "";
    dots = slides.map((_, i) => {
      const b = document.createElement("button");
      b.type = "button";
      // hs-dots kullanıyorsan class ver
      if (dotsWrap.classList.contains("hs-dots")) b.className = "hs-dot";
      b.setAttribute("aria-label", `Görsel ${i + 1}`);
      b.addEventListener("click", () => go(i));
      dotsWrap.appendChild(b);
      return b;
    });
  }

  function paintDots() {
    if (!dots.length) return;
    dots.forEach((d, i) => d.classList.toggle("active", i === index));
  }

  function clamp(i) {
    if (i < 0) return slides.length - 1;
    if (i >= slides.length) return 0;
    return i;
  }

  function getGapPx() {
    // flex gap (modern)
    const cs = getComputedStyle(track);
    const gap = cs.gap || cs.columnGap || "0px";
    const px = parseFloat(gap) || 0;
    return px;
  }

  function go(i) {
    index = clamp(i);

    const viewportW = viewport.clientWidth || 0;
    const gapPx = getGapPx();

    // ✅ her adım: viewport genişliği + gap
    const offset = index * (viewportW + gapPx);

    track.style.transform = `translateX(-${offset}px)`;
    paintDots();
  }

  if (prevBtn) prevBtn.addEventListener("click", () => go(index - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => go(index + 1));

  // swipe
  let startX = 0;
  let dragging = false;

  slider.addEventListener(
    "touchstart",
    (e) => {
      dragging = true;
      startX = e.touches[0].clientX;
    },
    { passive: true }
  );

  slider.addEventListener(
    "touchend",
    (e) => {
      if (!dragging) return;
      dragging = false;
      const endX = e.changedTouches[0].clientX;
      const dx = endX - startX;
      if (Math.abs(dx) < 40) return;
      if (dx < 0) go(index + 1);
      else go(index - 1);
    },
    { passive: true }
  );

  // resize fix
  window.addEventListener("resize", () => go(index));

  // init
  go(0);
})();
