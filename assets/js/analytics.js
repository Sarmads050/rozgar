/* RozgarJobs — privacy-friendly analytics loader.
 *
 * Nothing is loaded until data/site-config.json has an id in analytics.*,
 * so the site stays cookieless and makes zero third-party requests by default.
 *
 *   "analytics": {
 *     "goatcounter": "rozgarjobs",        → https://rozgarjobs.goatcounter.com
 *     "cloudflare_token": "",             → Cloudflare Web Analytics beacon
 *     "plausible_domain": "",             → optional, if you move to Plausible
 *     "track_search": true                → send the search term (no personal data)
 *   }
 *
 * GoatCounter is free for non-commercial use and shows: referrers, countries,
 * top job pages, and which search words brought people in.
 */
(function () {
  'use strict';

  var base = document.currentScript && document.currentScript.src
    ? document.currentScript.src.replace(/assets\/js\/analytics\.js.*$/, '')
    : '';

  function load(path, cfg) {
    fetch(base + 'data/site-config.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (site) {
        var a = (site && site.analytics) || {};
        window.__rozgarTrack = function (name, title) { return false; };

        if (a.goatcounter) {
          var host = a.goatcounter;
          if (host.indexOf('.') === -1) host += '.goatcounter.com';
          var s = document.createElement('script');
          s.async = true;
          s.src = 'https://gc.zgo.at/count.js';
          s.setAttribute('data-goatcounter', 'https://' + host + '/count');
          document.head.appendChild(s);
          window.goatcounter = window.goatcounter || {};
          if (a.track_search === false) {
            window.goatcounter.allow_local = false;
          }
          window.__rozgarTrack = function (name, title) {
            if (window.goatcounter && window.goatcounter.count) {
              window.goatcounter.count({ path: name, title: title, event: true });
            }
            return true;
          };
        }

        if (a.cloudflare_token) {
          var c = document.createElement('script');
          c.defer = true;
          c.src = 'https://static.cloudflareinsights.com/beacon.min.js';
          c.setAttribute('data-cf-beacon', JSON.stringify({ token: a.cloudflare_token }));
          document.head.appendChild(c);
        }

        if (a.plausible_domain) {
          var p = document.createElement('script');
          p.defer = true;
          p.setAttribute('data-domain', a.plausible_domain);
          p.src = 'https://plausible.io/js/script.js';
          document.head.appendChild(p);
        }
      })
      .catch(function () { /* analytics must never break the page */ });
  }

  /* Search terms and outbound apply clicks are the two things worth counting:
     they show which jobs people actually want and which sources convert. */
  function bindEvents() {
    document.addEventListener('submit', function (e) {
      var form = e.target;
      if (form && form.id === 'searchForm') {
        var q = document.getElementById('q');
        if (q && q.value.trim().length > 1) {
          track('/search/' + q.value.trim().toLowerCase().slice(0, 40));
        }
      }
    }, true);

    document.addEventListener('click', function (e) {
      var a = e.target.closest ? e.target.closest('a') : null;
      if (!a || !a.href) return;
      if (a.href.indexOf('http') === 0 && a.hostname !== location.hostname) {
        track('/out/' + a.hostname.replace(/^www\./, ''));
      }
    }, true);
  }

  function track(path, title) {
    if (window.__rozgarTrack) window.__rozgarTrack(path, title || path);
  }

  window.rozgarTrack = track;

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { load(); bindEvents(); });
  } else {
    load(); bindEvents();
  }
})();
