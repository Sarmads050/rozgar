/* RozgarJobs — Supabase client (no SDK, ~4 KB).
 *
 * The site works with Supabase switched off. When data/site-config.json has a
 * project URL and an anon key, three features wake up:
 *
 *   · Post a job       → inserts into job_submissions (status = 'pending')
 *   · Job alerts       → inserts into alert_subscribers (double opt-in later)
 *   · View counter     → calls rpc/record_view(job_slug)
 *   · Saved jobs       → syncs across devices using a local device id
 *
 * Only the ANON key ever reaches the browser. Row Level Security in
 * supabase/schema.sql is what stops a visitor from reading other rows.
 */
(function () {
  'use strict';

  var CFG = null;
  var BASE = document.currentScript && document.currentScript.src
    ? document.currentScript.src.replace(/assets\/js\/supabase-client\.js.*$/, '')
    : '';
  var ready = null;

  function load() {
    if (ready) return ready;
    ready = fetch(BASE + 'data/site-config.json', { cache: 'no-store' })
      .then(function (r) { return r.ok ? r.json() : {}; })
      .then(function (site) {
        var s = (site && site.supabase) || {};
        CFG = (s.url && s.anon_key) ? { url: s.url.replace(/\/$/, ''), key: s.anon_key } : null;
        return CFG;
      })
      .catch(function () { CFG = null; return null; });
    return ready;
  }

  function headers(extra) {
    var h = {
      apikey: CFG.key,
      Authorization: 'Bearer ' + CFG.key,
      'Content-Type': 'application/json'
    };
    if (extra) for (var k in extra) h[k] = extra[k];
    return h;
  }

  function insert(table, row) {
    return fetch(CFG.url + '/rest/v1/' + table, {
      method: 'POST',
      headers: headers({ Prefer: 'return=minimal' }),
      body: JSON.stringify(row)
    }).then(function (r) {
      if (r.ok) return { ok: true };
      return r.text().then(function (t) {
        return { ok: false, status: r.status, message: t.slice(0, 300) };
      });
    });
  }

  function select(path) {
    return fetch(CFG.url + '/rest/v1/' + path, { headers: headers() })
      .then(function (r) { return r.ok ? r.json() : []; })
      .catch(function () { return []; });
  }

  function rpc(fn, args) {
    return fetch(CFG.url + '/rest/v1/rpc/' + fn, {
      method: 'POST',
      headers: headers({ Prefer: 'return=minimal' }),
      body: JSON.stringify(args || {})
    }).then(function (r) { return r.ok; }).catch(function () { return false; });
  }

  /* One device id, generated locally, never linked to a person. */
  function deviceId() {
    var k = 'rozgar-device';
    var id = null;
    try { id = localStorage.getItem(k); } catch (e) {}
    if (!id) {
      id = 'd' + Math.random().toString(36).slice(2) + Date.now().toString(36);
      try { localStorage.setItem(k, id); } catch (e) {}
    }
    return id;
  }

  var api = {
    isConfigured: function () { return !!CFG; },
    ready: load,

    /* Employer form. Returns {ok:false, reason:'not-configured'} if Supabase
       is not set up yet, so the page can fall back to the GitHub issue form. */
    submitJob: function (job) {
      return load().then(function () {
        if (!CFG) return { ok: false, reason: 'not-configured' };
        var row = {
          title: job.title, company: job.company, sector: job.sector, city: job.city,
          vacancies: job.vacancies ? parseInt(job.vacancies, 10) || null : null,
          qualification: job.qualification || null,
          experience: job.experience || null,
          age_limit: job.age_limit || null,
          salary: job.salary || null,
          bps: job.bps || null,
          last_date: job.last_date,
          description: job.description,
          how_to_apply: job.how_to_apply || null,
          apply_url: job.apply_url || null,
          apply_email: job.apply_email || null,
          contact_name: job.contact_name || null,
          contact_email: job.contact_email,
          status: 'pending',
          user_agent: (navigator.userAgent || '').slice(0, 240)
        };
        return insert('job_submissions', row);
      });
    },

    /* Alert subscription. The email is confirmed by a link before any digest
       is sent, so a typo cannot subscribe a stranger. */
    subscribe: function (email, city, keyword) {
      return load().then(function () {
        if (!CFG) return { ok: false, reason: 'not-configured' };
        return insert('alert_subscribers', {
          email: email.trim().toLowerCase(),
          city: city || null,
          keyword: keyword || null,
          frequency: 'daily',
          confirmed: false,
          source: 'site'
        }).then(function (res) {
          /* a duplicate email is not an error for the visitor */
          if (!res.ok && res.status === 409) return { ok: true, duplicate: true };
          return res;
        });
      });
    },

    recordView: function (slug) {
      return load().then(function () {
        if (!CFG || !slug) return false;
        try {
          var k = 'viewed:' + slug;
          if (sessionStorage.getItem(k)) return false;   // once per tab
          sessionStorage.setItem(k, '1');
        } catch (e) {}
        return rpc('record_view', { slug: slug });
      });
    },

    viewsFor: function (slugs) {
      return load().then(function () {
        if (!CFG || !slugs || !slugs.length) return {};
        var list = slugs.slice(0, 40).map(function (s) { return '"' + s.replace(/"/g, '') + '"'; });
        return select('job_views?job_slug=in.(' + list.join(',') + ')&select=job_slug,views')
          .then(function (rows) {
            var out = {};
            (rows || []).forEach(function (r) { out[r.job_slug] = (out[r.job_slug] || 0) + r.views; });
            return out;
          });
      });
    },

    saveJob: function (slug) {
      return load().then(function () {
        if (!CFG) return false;
        return insert('saved_jobs', { device_id: deviceId(), job_slug: slug })
          .then(function (r) { return r.ok || r.status === 409; });
      });
    },

    unsaveJob: function (slug) {
      return load().then(function () {
        if (!CFG) return false;
        return fetch(CFG.url + '/rest/v1/saved_jobs?device_id=eq.' + encodeURIComponent(deviceId()) +
                     '&job_slug=eq.' + encodeURIComponent(slug),
                     { method: 'DELETE', headers: headers() })
          .then(function (r) { return r.ok; }).catch(function () { return false; });
      });
    },

    savedJobs: function () {
      return load().then(function () {
        if (!CFG) return [];
        return select('saved_jobs?device_id=eq.' + encodeURIComponent(deviceId()) +
                      '&select=job_slug,created_at')
          .then(function (rows) { return (rows || []).map(function (r) { return r.job_slug; }); });
      });
    }
  };

  window.RozgarDB = api;
})();
