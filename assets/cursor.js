(function () {
  "use strict";
  var doc = window.parent.document;
  var root = doc.documentElement;
  if (root.dataset.rrCursorReady === "true") return;
  root.dataset.rrCursorReady = "true";

  var ring = doc.createElement("div");
  var dot = doc.createElement("div");
  ring.className = "rr-cur rr-cur-ring";
  dot.className = "rr-cur rr-cur-dot";
  ring.setAttribute("aria-hidden", "true");
  dot.setAttribute("aria-hidden", "true");
  doc.body.appendChild(ring);
  doc.body.appendChild(dot);

  var mouseX = -100, mouseY = -100, ringX = -100, ringY = -100;
  var interactive = "a,button,input,[role='button'],[data-baseweb='slider']";

  function animate() {
    ringX += (mouseX - ringX) * 0.16;
    ringY += (mouseY - ringY) * 0.16;
    dot.style.transform = "translate3d(" + mouseX + "px," + mouseY + "px,0)";
    ring.style.transform = "translate3d(" + (ringX - 17) + "px," + (ringY - 17) + "px,0)";
    window.requestAnimationFrame(animate);
  }

  doc.addEventListener("mousemove", function (event) {
    mouseX = event.clientX;
    mouseY = event.clientY;
    root.classList.add("rr-cursor-live");
    root.classList.toggle("rr-cursor-hot", Boolean(event.target.closest(interactive)));
  }, { passive: true });
  doc.addEventListener("mousedown", function () { root.classList.add("rr-cursor-down"); });
  doc.addEventListener("mouseup", function () { root.classList.remove("rr-cursor-down"); });
  doc.addEventListener("mouseleave", function () { root.classList.remove("rr-cursor-live"); });
  animate();
}());
