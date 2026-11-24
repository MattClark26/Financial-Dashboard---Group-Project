/* Targeting cursor adapted from the user's eROdo project. */
(function () {
  'use strict';
  var root = document.documentElement;
  var ring = document.querySelector('.cur-ring');
  var dot = document.querySelector('.cur-dot');
  var fine = window.matchMedia('(hover: hover) and (pointer: fine)');
  var calm = window.matchMedia('(prefers-reduced-motion: reduce)');
  var enabled = false, raf = 0, seen = false;
  var mx = 0, my = 0, rx = 0, ry = 0;
  var rw = 34, rh = 34, tw = 34, th = 34, rr = 17, tr = 17;
  var target = null;
  var HOT = 'a,button,[role="button"],summary,label,select,input[type="range"],[data-act]';
  var TEXT = 'input:not([type=checkbox]):not([type=radio]):not([type=range]),textarea';

  function frame() {
    var k = calm.matches ? 1 : 0.2;
    var tx = mx, ty = my;
    if (target && target.isConnected) {
      var bounds = target.getBoundingClientRect();
      if (bounds.width && bounds.width < 420 && bounds.height < 130) {
        tx = bounds.left + bounds.width / 2; ty = bounds.top + bounds.height / 2;
        tw = bounds.width + 12; th = bounds.height + 12;
        tr = Math.min(parseFloat(getComputedStyle(target).borderRadius) || 10, th / 2) + 5;
      } else { tw = th = 52; tr = 26; }
    } else { tw = th = 34; tr = 17; }
    rx += (tx - rx) * k; ry += (ty - ry) * k;
    rw += (tw - rw) * k; rh += (th - rh) * k; rr += (tr - rr) * k;
    ring.style.transform = 'translate3d(' + (rx - rw / 2).toFixed(1) + 'px,' + (ry - rh / 2).toFixed(1) + 'px,0)';
    ring.style.width = rw.toFixed(1) + 'px'; ring.style.height = rh.toFixed(1) + 'px'; ring.style.borderRadius = rr.toFixed(1) + 'px';
    dot.style.transform = 'translate3d(' + mx + 'px,' + my + 'px,0)';
    raf = requestAnimationFrame(frame);
  }
  function onMove(event) {
    if (event.pointerType && event.pointerType !== 'mouse' && event.pointerType !== 'pen') return;
    mx = event.clientX; my = event.clientY;
    if (!seen) { seen = true; rx = mx; ry = my; root.classList.add('cur-live'); }
    var element = event.target && event.target.closest ? event.target : null;
    var text = element && element.closest(TEXT);
    var hot = !text && element && element.closest(HOT);
    if (hot && (hot.disabled || hot.getAttribute('aria-disabled') === 'true')) hot = null;
    target = hot || null;
    root.classList.toggle('cur-hot', !!hot); root.classList.toggle('cur-text', !!text);
  }
  function start() {
    if (enabled || !fine.matches) return;
    enabled = true; root.classList.add('cur-on');
    window.addEventListener('pointermove', onMove, { passive: true });
    window.addEventListener('pointerdown', function () { root.classList.add('cur-down'); }, { passive: true });
    window.addEventListener('pointerup', function () { root.classList.remove('cur-down'); }, { passive: true });
    document.addEventListener('mouseleave', function () { root.classList.remove('cur-live'); seen = false; });
    raf = requestAnimationFrame(frame);
  }
  function stop() {
    if (!enabled) return;
    enabled = false; cancelAnimationFrame(raf);
    root.classList.remove('cur-on', 'cur-live', 'cur-hot', 'cur-text', 'cur-down');
  }
  fine.addEventListener('change', function () { fine.matches ? start() : stop(); });
  start();
})();
