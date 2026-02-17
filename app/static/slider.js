document.addEventListener("DOMContentLoaded", () => {
  const track = document.getElementById("hsTrack");
  if (!track) return;

  const slides = Array.from(track.children);
  const prevBtn = document.getElementById("hsPrev");
  const nextBtn = document.getElementById("hsNext");
  const dotsWrap = document.getElementById("hsDots");

  let index = 0;

  // DOTS oluştur
  slides.forEach((_, i) => {
    const dot = document.createElement("button");
    dot.className = "hs-dot";
    if (i === 0) dot.classList.add("active");
    dot.addEventListener("click", () => goTo(i));
    dotsWrap.appendChild(dot);
  });

  const dots = Array.from(dotsWrap.children);

  function update(){
    track.style.transform = `translateX(-${index * 100}%)`;
    dots.forEach(d => d.classList.remove("active"));
    dots[index].classList.add("active");
  }

  function goTo(i){
    index = i;
    update();
  }

  function next(){
    index = (index + 1) % slides.length;
    update();
  }

  function prev(){
    index = (index - 1 + slides.length) % slides.length;
    update();
  }

  nextBtn.addEventListener("click", next);
  prevBtn.addEventListener("click", prev);

  // AUTO SLIDE
  setInterval(next, 4500);
});
