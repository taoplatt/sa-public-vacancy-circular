/* Consent-gated Meta pixel. The banner only exists in the page when a pixel
   id is configured (see base.html); GoatCounter is cookieless and loads
   unconditionally. Progressive enhancement: with JS off, no banner, no
   pixel, and the site works fully. */
(function () {
  var KEY = "mm-consent";
  var body = document.body;
  var pixelId = body.getAttribute("data-pixel-id");
  var eventName = body.getAttribute("data-pixel-event") || "PageView";
  var banner = document.getElementById("consent");
  if (!pixelId || !banner) return;

  function loadPixel() {
    if (window.fbq) return;
    !(function (f, b, e, v, n, t, s) {
      if (f.fbq) return; n = f.fbq = function () {
        n.callMethod ? n.callMethod.apply(n, arguments) : n.queue.push(arguments);
      };
      if (!f._fbq) f._fbq = n; n.push = n; n.loaded = !0; n.version = "2.0";
      n.queue = []; t = b.createElement(e); t.async = !0; t.src = v;
      s = b.getElementsByTagName(e)[0]; s.parentNode.insertBefore(t, s);
    })(window, document, "script", "https://connect.facebook.net/en_US/fbevents.js");
    window.fbq("init", pixelId);
    window.fbq("track", "PageView");
    if (eventName !== "PageView") window.fbq("track", eventName);
  }

  var choice = null;
  try { choice = localStorage.getItem(KEY); } catch (e) {}

  if (choice === "yes") { loadPixel(); return; }
  if (choice === "no") return;

  banner.hidden = false;
  document.getElementById("consent-yes").addEventListener("click", function () {
    try { localStorage.setItem(KEY, "yes"); } catch (e) {}
    banner.hidden = true;
    loadPixel();
  });
  document.getElementById("consent-no").addEventListener("click", function () {
    try { localStorage.setItem(KEY, "no"); } catch (e) {}
    banner.hidden = true;
  });
})();
