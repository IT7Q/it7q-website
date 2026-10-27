// IT7Q forms: validation, Turnstile and posting to the webhooks (PLAN.md §4, §4.12).
// Strict CSP: no inline handlers, and no HTML strings (textContent only).
(function () {
  "use strict";
  var CFG = window.IT7Q_CONFIG || {};
  var TIMEOUT_MS = 15000;
  var EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
  var loadedAt = Date.now();
  var handlers = {};
  var ts = { state: "idle", queue: [] }; // idle | loading | ready | failed

  // POST JSON. Always resolves {status, data}: status 0 = network error or timeout,
  // data undefined = the reply wasn't valid JSON.
  function post(hook, body) {
    var ctrl = new AbortController();
    var timer = setTimeout(function () { ctrl.abort(); }, TIMEOUT_MS);
    return fetch(CFG.hooks + "/" + hook, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
      credentials: "omit",
      cache: "no-store"
    }).then(function (res) {
      return res.text().then(function (text) {
        var data;
        try { data = text ? JSON.parse(text) : null; } catch (e) { data = undefined; }
        return { status: res.status, data: data };
      });
    }).catch(function () {
      return { status: 0, data: null };
    }).finally(function () {
      clearTimeout(timer);
    });
  }

  function showStatus(box, kind, text) {
    box.hidden = !text;
    box.className = "form__status" + (kind ? " form__status--" + kind : "");
    box.textContent = text || "";
  }

  // ------------------------------------------------------------ Turnstile

  function loadTurnstile(cb) {
    if (ts.state === "ready" || ts.state === "failed") { cb(ts.state === "ready"); return; }
    ts.queue.push(cb);
    if (ts.state === "loading") return;
    ts.state = "loading";
    function done(ok) {
      ts.state = ok ? "ready" : "failed";
      ts.queue.splice(0).forEach(function (fn) { fn(ok); });
    }
    window.it7qTurnstileReady = function () { done(true); };
    var s = document.createElement("script");
    s.src = "https://challenges.cloudflare.com/turnstile/v0/api.js?render=explicit&onload=it7qTurnstileReady";
    s.async = true;
    s.addEventListener("error", function () { done(false); });
    document.head.appendChild(s);
  }

  function setupTurnstile(form) {
    var box = form.querySelector(".turnstile");
    var t = { token: "", id: null, broken: false };
    if (CFG.mock) {
      t.token = "mock-token";
      box.textContent = "Security check skipped: local mock build.";
      box.className += " turnstile--mock";
    } else if (!CFG.turnstileSiteKey) {
      t.broken = true; // fail closed: never send without a real check
    } else {
      loadTurnstile(function (ok) {
        if (!ok || !window.turnstile) { t.broken = true; return; }
        t.id = window.turnstile.render(box, {
          sitekey: CFG.turnstileSiteKey,
          action: form.getAttribute("data-turnstile-action"),
          callback: function (token) { t.token = token; },
          "expired-callback": function () { t.token = ""; },
          "error-callback": function () { t.token = ""; }
        });
      });
    }
    t.reset = function () {
      if (!CFG.mock && t.id !== null && window.turnstile) {
        window.turnstile.reset(t.id);
        t.token = "";
      }
    };
    return t;
  }

  // ------------------------------------------------------------ fields

  function controls(form) {
    return Array.prototype.slice.call(form.querySelectorAll("input[name], select[name], textarea[name]"));
  }

  function collect(form) {
    var body = {};
    controls(form).forEach(function (el) {
      if (el.type === "checkbox") body[el.name] = el.checked;
      else if (el.type === "password") body[el.name] = el.value;
      else body[el.name] = el.value.trim();
    });
    return body;
  }

  function setError(el, text) {
    var err = document.getElementById(el.id + "-err");
    if (text) el.setAttribute("aria-invalid", "true");
    else el.removeAttribute("aria-invalid");
    if (err) {
      err.textContent = text || "";
      err.hidden = !text;
    }
  }

  function norm(s) {
    return s.trim().replace(/\s+/g, " ").toLowerCase();
  }

  function validate(form) {
    var bad = [];
    controls(form).forEach(function (el) {
      if (el.name === "website") return;
      var msg = "";
      var value = el.type === "checkbox" ? el.checked : el.value.trim();
      var max = parseInt(el.getAttribute("maxlength") || "0", 10);
      if (el.required && !value) {
        msg = el.type === "checkbox" ? "Please tick this box to continue." : "Please fill this in.";
      } else if (el.type === "email" && value && !EMAIL.test(value)) {
        msg = "Please enter a valid email address.";
      } else if (max && typeof value === "string" && value.length > max) {
        msg = "Please keep this under " + max + " characters.";
      } else if (el.hasAttribute("data-match") && value) {
        var other = document.getElementById(el.getAttribute("data-match"));
        if (other && norm(other.value) !== norm(el.value)) msg = "Your signature must match your full name exactly.";
      }
      setError(el, msg);
      if (msg) bad.push(el);
    });
    return bad;
  }

  // ------------------------------------------------------------ results

  function defaultResult(r, form, status) {
    if (r.status === 200 || r.status === 202) {
      form.reset();
      form.querySelector(".form__fields").hidden = true;
      showStatus(status, "ok", form.getAttribute("data-success"));
      status.focus();
    } else if (r.status === 400) {
      showStatus(status, "error", "Some details weren't accepted. Please check the form and try again.");
    } else if (r.status === 429) {
      showStatus(status, "error", "Too many attempts. Please wait a few minutes and try again.");
    } else {
      showStatus(status, "error", "We couldn't send this just now. Please try again, or call or email us instead.");
    }
  }

  function setupForm(form) {
    var key = form.getAttribute("data-form");
    var hook = form.getAttribute("data-hook");
    var status = form.querySelector(".form__status");
    var button = form.querySelector("button[type=submit]");
    var check = setupTurnstile(form);

    form.addEventListener("submit", function (e) {
      e.preventDefault();
      if (form.getAttribute("aria-busy") === "true") return;
      var bad = validate(form);
      if (bad.length) {
        showStatus(status, "error", "Please fix the highlighted " + (bad.length === 1 ? "field." : "fields."));
        bad[0].focus();
        return;
      }
      if (check.broken) {
        showStatus(status, "error", "The security check couldn't load, so this form can't be sent right now. Please call or email us instead.");
        return;
      }
      if (!check.token) {
        showStatus(status, "error", "Please complete the security check first.");
        return;
      }
      var body = collect(form);
      body.turnstile = check.token;
      body.elapsed_ms = Date.now() - loadedAt;
      var h = handlers[key] || {};
      if (h.extra) h.extra(body);

      form.setAttribute("aria-busy", "true");
      button.disabled = true;
      showStatus(status, "info", "Sending…");
      post(hook, body).then(function (r) {
        form.removeAttribute("aria-busy");
        button.disabled = false;
        check.reset();
        if (h.result && h.result(r, form, status)) return;
        defaultResult(r, form, status);
      });
    });
  }

  // Pre-select a service from ?topic= (e.g. the coming-soon card's "Tell me when it's ready")
  function applyTopic() {
    var topic = new URLSearchParams(window.location.search).get("topic");
    var select = document.querySelector("select[name=service]");
    if (!topic || !select) return;
    Array.prototype.forEach.call(select.options, function (o) {
      if (o.value === topic) select.value = topic;
    });
  }

  window.IT7QForms = {
    register: function (key, h) { handlers[key] = h; },
    post: post,
    showStatus: showStatus
  };

  document.addEventListener("DOMContentLoaded", function () {
    Array.prototype.forEach.call(document.querySelectorAll("form[data-form]"), setupForm);
    applyTopic();
    if (CFG.mock) {
      var banner = document.createElement("p");
      banner.className = "mock-banner";
      banner.textContent = "Local mock build: forms and logins talk to tools/preview.py, not the real server.";
      document.body.insertBefore(banner, document.body.firstChild);
    }
  });
})();
