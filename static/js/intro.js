/**
 * NitroFind — Scrollytelling intro controller
 *
 * Instant WebP poster on a fullscreen white stage, crossfading into an
 * all-intra scroll-scrubbed video (car disassembles then reassembles),
 * followed by a white->dark veil that reveals the existing .home-view
 * (never duplicated). Also drives a subtle mouse parallax on the stage.
 *
 * Contract (see templates/index.html + static/css/style.css section 12):
 * - html[data-intro] = "active" | "done" (set in <head>, before paint)
 * - .intro-scroller > .intro-stage > #intro-poster, #intro-video, .intro-veil, .intro-hint
 * - .home-view is the reveal target (owned by app.js state machine)
 * - app.js is NEVER modified; coupling is via body[data-state] MutationObserver only.
 *
 * Vanilla JS only. No libraries, no CDN.
 */
(function () {
  "use strict";

  // -----------------------------------------------------------------------
  // Pure helpers
  // -----------------------------------------------------------------------

  function clamp(value, min, max) {
    return Math.min(max, Math.max(min, value));
  }

  function lerp(from, to, t) {
    return from + (to - from) * t;
  }

  // Disassemble 0 -> duration over p:[0, 0.5]; reassemble duration -> 0 over p:[0.5, 1]
  function mapProgressToTime(p, duration) {
    if (p <= 0.5) {
      return (p / 0.5) * duration;
    }
    return (1 - (p - 0.5) / 0.5) * duration;
  }

  function isFullyBuffered(video, duration) {
    var buffered = video.buffered;
    if (!buffered || buffered.length === 0) {
      return false;
    }
    var lastEnd = buffered.end(buffered.length - 1);
    return lastEnd >= duration - 0.3;
  }

  // -----------------------------------------------------------------------
  // Guard: only run when the intro is meant to play (prefers-reduced-motion
  // and "already done" both leave the home view fully static).
  // -----------------------------------------------------------------------

  if (document.documentElement.dataset.intro !== "active") {
    return;
  }

  var scroller = document.querySelector(".intro-scroller");
  var stage = document.querySelector(".intro-stage");
  var poster = document.getElementById("intro-poster");
  var video = document.getElementById("intro-video");
  var veil = document.querySelector(".intro-veil");
  var hint = document.querySelector(".intro-hint");
  var homeView = document.querySelector(".home-view");

  if (!scroller || !stage || !poster || !video || !veil || !hint || !homeView) {
    finishIntro();
    return;
  }

  // -----------------------------------------------------------------------
  // State
  // -----------------------------------------------------------------------

  var duration = 10; // fallback seconds, replaced once metadata loads
  var renderedTime = 0;
  var lastAssignedTime = -1;
  var rafId = null;
  var running = true;
  var finished = false;

  var parallaxTargetX = 0;
  var parallaxTargetY = 0;
  var parallaxCurrentX = 0;
  var parallaxCurrentY = 0;

  var TIME_EPSILON = 0.02;
  var LERP_RATE = 0.14;
  var PARALLAX_RANGE = 8; // px

  // -----------------------------------------------------------------------
  // Video setup
  // -----------------------------------------------------------------------

  video.addEventListener("loadedmetadata", function () {
    if (video.duration && isFinite(video.duration) && video.duration > 0) {
      duration = video.duration;
    }
  });

  var crossfadeTimeoutId = null;

  function markVideoReady() {
    if (video.classList.contains("ready")) {
      return;
    }
    video.classList.add("ready");
    if (crossfadeTimeoutId !== null) {
      clearTimeout(crossfadeTimeoutId);
      crossfadeTimeoutId = null;
    }
  }

  function checkBuffered() {
    if (isFullyBuffered(video, duration)) {
      markVideoReady();
    }
  }

  video.addEventListener("progress", checkBuffered);
  video.addEventListener("canplaythrough", checkBuffered);
  video.addEventListener("canplay", function () {
    // Fallback: some browsers never fire a "fully buffered" progress event
    // even though playback (and seeking) is perfectly fine. Give it a beat,
    // then crossfade anyway so the user is never stuck on the poster.
    if (crossfadeTimeoutId === null && !video.classList.contains("ready")) {
      crossfadeTimeoutId = setTimeout(markVideoReady, 1200);
    }
  });

  video.addEventListener("error", function () {
    // Robustness: video failed to load/decode. Leave the poster visible;
    // the veil + reveal + scroll must keep working over the static poster.
    // Nothing else to do here — we simply never mark .ready, and the rAF
    // loop below already guards every video access behind readyState checks.
  });

  // -----------------------------------------------------------------------
  // Scroll progress + rAF loop
  // -----------------------------------------------------------------------

  function getProgress() {
    var scrollableHeight = scroller.offsetHeight - window.innerHeight;
    if (scrollableHeight <= 0) {
      return 1;
    }
    return clamp(window.scrollY / scrollableHeight, 0, 1);
  }

  function applyVeilAndReveal(progress) {
    // Veil: 0 -> 1 opacity as progress goes 0.82 -> 0.95
    var veilT = clamp((progress - 0.82) / (0.95 - 0.82), 0, 1);
    veil.style.opacity = String(veilT);

    // Home-view reveal: opacity + translateY as progress goes 0.86 -> 1.0
    var revealT = clamp((progress - 0.86) / (1.0 - 0.86), 0, 1);
    homeView.style.opacity = String(revealT);
    var translateY = lerp(24, 0, revealT);
    homeView.style.transform = "translateY(" + translateY + "px)";
    homeView.style.pointerEvents = revealT >= 0.9 ? "auto" : "none";
  }

  function applyParallax() {
    parallaxCurrentX = lerp(parallaxCurrentX, parallaxTargetX, LERP_RATE);
    parallaxCurrentY = lerp(parallaxCurrentY, parallaxTargetY, LERP_RATE);
    var x = parallaxCurrentX * PARALLAX_RANGE;
    var y = parallaxCurrentY * PARALLAX_RANGE;
    var rotate = parallaxCurrentX * 0.6; // tiny tilt, degrees
    stage.style.transform =
      "translate3d(" + x.toFixed(2) + "px, " + y.toFixed(2) + "px, 0) rotate(" + rotate.toFixed(2) + "deg)";
  }

  function applyVideoTime(progress) {
    var targetTime = mapProgressToTime(progress, duration);
    renderedTime = lerp(renderedTime, targetTime, LERP_RATE);

    var canSeek = video.readyState >= 2 && !video.seeking;
    if (canSeek && Math.abs(renderedTime - lastAssignedTime) > TIME_EPSILON) {
      try {
        video.currentTime = renderedTime;
        lastAssignedTime = renderedTime;
      } catch (err) {
        // Seeking can throw in some browsers if metadata isn't ready yet;
        // ignore and retry on the next frame.
      }
    }
  }

  function tick() {
    if (!running) {
      return;
    }

    var progress = getProgress();

    applyVideoTime(progress);
    applyVeilAndReveal(progress);
    applyParallax();

    if (progress >= 0.995) {
      finishIntro();
      return;
    }

    rafId = window.requestAnimationFrame(tick);
  }

  function startLoop() {
    if (rafId === null && running) {
      rafId = window.requestAnimationFrame(tick);
    }
  }

  function stopLoop() {
    running = false;
    if (rafId !== null) {
      window.cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  // -----------------------------------------------------------------------
  // Scroll hint
  // -----------------------------------------------------------------------

  function onScroll() {
    if (window.scrollY > 40) {
      hint.style.opacity = "0";
    }
  }

  // -----------------------------------------------------------------------
  // Mouse parallax input (event only stores the target; rAF loop consumes it)
  // -----------------------------------------------------------------------

  function onMouseMove(event) {
    var cx = window.innerWidth / 2;
    var cy = window.innerHeight / 2;
    parallaxTargetX = clamp((event.clientX - cx) / cx, -1, 1);
    parallaxTargetY = clamp((event.clientY - cy) / cy, -1, 1);
  }

  // -----------------------------------------------------------------------
  // Completion / finish path
  // -----------------------------------------------------------------------

  function finishIntro() {
    if (finished) {
      return;
    }
    finished = true;

    document.documentElement.dataset.intro = "done";

    homeView.style.opacity = "";
    homeView.style.transform = "";
    homeView.style.pointerEvents = "";

    stopLoop();

    window.removeEventListener("scroll", onScroll);
    window.removeEventListener("mousemove", onMouseMove);

    window.scrollTo(0, 0);
  }

  // -----------------------------------------------------------------------
  // Leaving home: any state change away from "home" cleanly consumes the
  // intro so returning to home later shows the search centered, with no
  // forced re-scroll. Zero changes required to app.js.
  // -----------------------------------------------------------------------

  var stateObserver = new MutationObserver(function () {
    if (document.body.dataset.state !== "home") {
      finishIntro();
    }
  });
  stateObserver.observe(document.body, { attributes: true, attributeFilter: ["data-state"] });

  // -----------------------------------------------------------------------
  // Wire up + start
  // -----------------------------------------------------------------------

  window.addEventListener("scroll", onScroll, { passive: true });
  window.addEventListener("mousemove", onMouseMove, { passive: true });

  startLoop();
}());
