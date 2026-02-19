(() => {
  const slider = document.querySelector(".hero-slider");
  if (!slider) return;

  const viewport = slider.querySelector(".hs-viewport");
  const track = slider.querySelector(".hs-track");
  if (!viewport || !track) return;

  // 1) img'leri slide wrapper içine al (blur bg için)
  const imgs = Array.from(track.querySelectorAll("img"));
  if (!imgs.length) return;

  // Eğer daha önce sarıldıysa tekrar sarmayalım
  const alreadyWrapped = track.querySelector(".hs-slide");
  if (!alreadyWrapped) {
    imgs.forEach((img) => {
      const wrap = document.createElement("div");
      wrap.className = "hs-slide";
      wrap.style.setProperty("--bg", `url("${img.getAttribute("src")}")`);

      // img'yi wrap içine taşı
      img.parentNode.insertBefore(wrap, img);
      wrap.appendChild(img);
    });
  } else {
    // wrapped ise bg değişkenini set et
    track.querySelectorAll(".hs-slide").forEach((wrap) => {
      const img = wrap.querySelector("img");
      if (img) wrap.style.setProperty("--bg", `url("${img.getAttribute("src")}")`);
    });
  }

  const slides = Array.from(track.querySelectorAll(".hs-slide"));
  const prevBtn = slider.querySelector("#hsPrev") || slider.querySelector(".hs-btn.prev");
  const nextBtn = slider.querySelector("#hsNext") || slider.querySelector(".hs-btn.next");
  const dotsWrap = slider.querySelector("#hsDots") || slider.querySelector(".hs-dots");

  let index = 0;

  // 2) dots
  let dots = [];
  if (dotsWrap) {
    dotsWrap.innerHTML = "";
    dots = slides.map((_, i) => {
      const b = document.createElement("button");
      b.type = "button";
      b.className = "hs-dot";
      b.setAttribute("aria-label", `Görsel ${i + 1}`);
      b.addEventListener("click", () => go(i));
      dotsWrap.appendChild(b);
      return b;
    });
  }

  function paintDots() {
    dots.forEach((d, i) => d.classList.toggle("active", i === index));
  }

  function clamp(i) {
    if (i < 0) return slides.length - 1;
    if (i >= slides.length) return 0;
    return i;
  }

  function go(i) {
    index = clamp(i);
    const w = viewport.clientWidth;
    viewport.scrollTo({ left: index * w, behavior: "smooth" });
    paintDots();
  }

  // 3) buttons
  if (prevBtn) prevBtn.addEventListener("click", () => go(index - 1));
  if (nextBtn) nextBtn.addEventListener("click", () => go(index + 1));

  // 4) scroll ile index güncelle (swipe sonrası dot doğru kalsın)
  let raf = 0;
  viewport.addEventListener("scroll", () => {
    cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => {
      const w = viewport.clientWidth || 1;
      const newIndex = Math.round(viewport.scrollLeft / w);
      if (newIndex !== index) {
        index = clamp(newIndex);
        paintDots();
      }
    });
  }, { passive: true });

  // resize sonrası aynı slide’a hizala
  window.addEventListener("resize", () => go(index));

  // init
  go(0);
})();
// Sticky CTA show/hide on scroll (safe on all pages)
(function(){
  const cta = document.querySelector('.sticky-cta');
  if(!cta) return;

  function onScroll(){
    const y = window.scrollY || document.documentElement.scrollTop || 0;
    cta.classList.toggle('is-visible', y > 200);
  }
  window.addEventListener('scroll', onScroll, { passive:true });
  onScroll();
})();
