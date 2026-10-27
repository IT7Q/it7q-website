// IT7Q NDA area: login session, locked panels and the gated-detail renderer (PLAN.md §4.5, §4.6).
// Fail closed: the page ships locked and only unlocks on a 200 with valid JSON.
// Gated detail is built with DOM APIs and textContent only.
(function () {
  "use strict";
  var CFG = window.IT7Q_CONFIG || {};
  var F = window.IT7QForms;
  var KEY = "it7q.session";
  var MAX_SECTIONS = 30, MAX_ITEMS = 50, MAX_TEXT = 4000;

  // ------------------------------------------------------------ session (sessionStorage: this tab only)

  function clearSession() {
    try { sessionStorage.removeItem(KEY); } catch (e) { /* storage blocked */ }
  }

  function getSession() {
    var s = null;
    try { s = JSON.parse(sessionStorage.getItem(KEY) || "null"); } catch (e) { s = null; }
    if (!s || typeof s.token !== "string" || typeof s.email !== "string" || typeof s.expires_at !== "number") return null;
    if (Date.now() >= s.expires_at) { clearSession(); return null; }
    return s;
  }

  function saveSession(d) {
    var expires = Date.parse(d.expires_at);
    if (typeof d.token !== "string" || d.token.length < 20 || typeof d.email !== "string" || !isFinite(expires)) return false;
    try {
      sessionStorage.setItem(KEY, JSON.stringify({
        token: d.token, email: d.email, expires_at: expires, investor: d.investor === true
      }));
      return true;
    } catch (e) {
      return false;
    }
  }

  function logout() {
    var s = getSession();
    if (s) F.post("nda-content", { token: s.token, action: "logout" }); // best effort; the token is dropped either way
    clearSession();
  }

  // ------------------------------------------------------------ DOM helpers

  function el(tag, cls, text) {
    var n = document.createElement(tag);
    if (cls) n.className = cls;
    if (typeof text === "string") n.textContent = text.slice(0, MAX_TEXT);
    return n;
  }

  function isText(v) {
    return typeof v === "string" && v.trim() !== "";
  }

  // sections: [{heading, paragraphs: [..], items: [..]}]
  function renderSections(parent, sections, headingTag) {
    if (!Array.isArray(sections)) return;
    sections.slice(0, MAX_SECTIONS).forEach(function (sec) {
      if (!sec || typeof sec !== "object") return;
      if (isText(sec.heading)) parent.appendChild(el(headingTag, "lock__h", sec.heading));
      if (Array.isArray(sec.paragraphs)) {
        sec.paragraphs.slice(0, MAX_ITEMS).forEach(function (p) { if (isText(p)) parent.appendChild(el("p", null, p)); });
      }
      if (Array.isArray(sec.items)) {
        var ul = el("ul");
        sec.items.slice(0, MAX_ITEMS).forEach(function (i) { if (isText(i)) ul.appendChild(el("li", null, i)); });
        if (ul.childNodes.length) parent.appendChild(ul);
      }
    });
  }

  function watermark(body, viewer) {
    body.setAttribute("data-viewer", "Confidential · " + viewer);
    body.appendChild(el("p", "lock__mark", "Confidential: shared with " + viewer + " under NDA."));
  }

  function projectDetail(d, viewer) {
    var details = el("details", "lock__details");
    details.appendChild(el("summary", null, "Full details (confidential)"));
    var body = el("div", "lock__body");
    if (isText(d.summary)) body.appendChild(el("p", null, d.summary));
    renderSections(body, d.sections, "h4");
    watermark(body, viewer);
    details.appendChild(body);
    return details;
  }

  // ------------------------------------------------------------ locking

  function relock() {
    Array.prototype.forEach.call(document.querySelectorAll(".lock__details"), function (n) { n.remove(); });
    Array.prototype.forEach.call(document.querySelectorAll(".lock__locked"), function (n) { n.hidden = false; });
    var inv = document.getElementById("investor-content");
    if (inv) {
      Array.prototype.forEach.call(inv.querySelectorAll(".lock__body"), function (n) { n.remove(); });
      var locked = inv.querySelector(".lock__locked");
      if (locked) locked.hidden = false;
    }
  }

  function unlockDivision(data, viewer) {
    if (!data.projects || typeof data.projects !== "object" || Array.isArray(data.projects)) return false;
    var count = 0;
    Array.prototype.forEach.call(document.querySelectorAll(".lock[data-project]"), function (lock) {
      var d = Object.prototype.hasOwnProperty.call(data.projects, lock.getAttribute("data-project"))
        ? data.projects[lock.getAttribute("data-project")] : null;
      if (!d || typeof d !== "object") return;
      lock.querySelector(".lock__locked").hidden = true;
      lock.appendChild(projectDetail(d, viewer));
      count += 1;
    });
    return count > 0;
  }

  function unlockInvestors(data, viewer) {
    var box = document.getElementById("investor-content");
    if (!box || !Array.isArray(data.sections)) return false;
    var body = el("div", "lock__body lock__body--page");
    renderSections(body, data.sections, "h2");
    if (!body.childNodes.length) return false;
    watermark(body, viewer);
    box.querySelector(".lock__locked").hidden = true;
    box.appendChild(body);
    return true;
  }

  function setupBar(bar) {
    var division = bar.getAttribute("data-division");
    var msg = bar.querySelector(".nda-bar__msg");
    var retry = bar.querySelector(".nda-bar__retry");

    function say(text, showRetry) {
      msg.textContent = text;
      retry.hidden = !showRetry;
    }

    function load() {
      var s = getSession();
      relock();
      if (!s) { bar.hidden = true; return; }
      bar.hidden = false;
      say("Logged in as " + s.email + ". Loading full details…", false);
      F.post("nda-content", { token: s.token, division: division }).then(function (r) {
        var d = r.data;
        if (r.status === 200 && d && typeof d === "object" && d.division === division) {
          var viewer = isText(d.viewer) ? d.viewer : s.email;
          var ok = division === "investors" ? unlockInvestors(d, viewer) : unlockDivision(d, viewer);
          if (ok) { say("Logged in as " + s.email + ". Full details unlocked. Please keep them confidential.", false); return; }
        }
        relock();
        if (r.status === 401) {
          clearSession();
          bar.hidden = true;
          showNotice("Your session has ended. Please log in again to see full details.");
        } else if (r.status === 403) {
          say("Logged in as " + s.email + ". Your access doesn't include this area.", false);
        } else {
          say("We couldn't load the full details just now.", true);
        }
      });
    }

    retry.addEventListener("click", load);
    bar.querySelector(".nda-bar__logout").addEventListener("click", function () {
      logout();
      relock();
      bar.hidden = true;
      showNotice("You've logged out.");
    });
    load();
  }

  function showNotice(text) {
    var bar = document.querySelector(".nda-bar");
    var note = document.querySelector(".nda-notice");
    if (!note) {
      note = el("p", "nda-notice");
      note.setAttribute("role", "status");
      bar.parentNode.insertBefore(note, bar.nextSibling);
    }
    note.textContent = text + " ";
    var a = el("a", null, "Log in");
    a.href = "/access/?next=" + encodeURIComponent(window.location.pathname);
    note.appendChild(a);
  }

  // ------------------------------------------------------------ /access/ page

  function safeNext() {
    var next = new URLSearchParams(window.location.search).get("next") || "";
    return /^\/(?!\/)[A-Za-z0-9\-\/]*$/.test(next) ? next : "";
  }

  function setupAccess() {
    var signedIn = document.getElementById("nda-signed-in");
    var login = document.getElementById("nda-login");
    if (!signedIn || !login) return;

    function show() {
      var s = getSession();
      signedIn.hidden = !s;
      login.hidden = !!s;
      if (s) {
        signedIn.querySelector(".nda-email").textContent = s.email;
        signedIn.querySelector(".nda-investors").hidden = !s.investor;
      }
    }

    signedIn.querySelector(".nda-logout").addEventListener("click", function () {
      logout();
      show();
    });

    F.register("nda_login", {
      result: function (r, form, status) {
        if (r.status === 200 && r.data && typeof r.data === "object") {
          if (!saveSession(r.data)) {
            F.showStatus(status, "error", "Logged in, but your browser blocked session storage, so we can't keep you logged in. Please allow site data for it7q.com.au and try again.");
            return true;
          }
          form.reset();
          var next = safeNext();
          if (next) { window.location.assign(next); return true; }
          F.showStatus(status, "", "");
          show();
          signedIn.focus();
          return true;
        }
        if (r.status === 401) {
          F.showStatus(status, "error", "That email and password didn't work, or your access isn't active. Check them and try again.");
          return true;
        }
        return false; // 429, network and server errors: default messages
      }
    });
    show();
  }

  F.register("nda_request", {
    extra: function (body) {
      body.nda_version = CFG.ndaVersion;
      body.nda_sha256 = CFG.ndaSha256;
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    setupAccess();
    var bar = document.querySelector(".nda-bar[data-division]");
    if (bar) setupBar(bar);
  });
})();
