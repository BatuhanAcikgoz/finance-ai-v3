// login.js — single-purpose sign-in screen. No localStorage, no tokens.
// Backend issues an HttpOnly `fasess` cookie on POST /v1/auth/login.
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);
  const form = $("login-form");
  const errBox = $("login-error");
  const submit = $("login-submit");
  const showBtn = $("login-show");
  const pwd = $("login-password");
  const host = $("login-host");

  // Friendly host label in the side card.
  if (host) {
    host.textContent = location.host || "127.0.0.1:8080";
  }

  // 👁 toggle for password field — purely visual.
  if (showBtn && pwd) {
    showBtn.addEventListener("click", () => {
      pwd.type = pwd.type === "password" ? "text" : "password";
    });
  }

  function showError(msg) {
    errBox.textContent = msg;
    errBox.hidden = !msg;
  }

  // Friendly mapping of known backend errors to human-readable guidance.
  // Anything not in this map falls through to the backend's own message.
  function friendly(msg) {
    if (!msg) return "Giriş başarısız.";
    const m = String(msg).toLowerCase();
    if (m.includes("invalid credentials") || m.includes("invalid session")) {
      return "Kullanıcı adı veya parola hatalı. (Varsayılan: admin / admin)";
    }
    if (m.includes("user disabled")) {
      return "Bu kullanıcı devre dışı bırakılmış.";
    }
    if (m.includes("network") || m.includes("failed to fetch")) {
      return "Sunucuya ulaşılamıyor. Ağ bağlantınızı kontrol edin.";
    }
    return msg;
  }

  async function postJSON(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    const text = await r.text();
    let data = null;
    try { data = text ? JSON.parse(text) : null; } catch (_) { /* ignore */ }
    if (!r.ok) {
      const detail = (data && (data.detail || data.error)) || r.statusText || "giriş başarısız";
      throw new Error(friendly(detail));
    }
    return data;
  }

  async function postForm(url, body) {
    const r = await fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body || {}),
    });
    return r.ok;
  }

  // ---- Sign-in ----------------------------------------------------------
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    showError("");
    const username = $("login-username").value.trim();
    const password = $("login-password").value;
    if (!username || !password) {
      showError("Kullanıcı adı ve parola gerekli.");
      return;
    }
    submit.disabled = true;
    submit.classList.add("is-loading");
    try {
      const resp = await postJSON("/api/v1/auth/login", { username, password });
      if (resp && resp.must_change_password) {
        // Show the rotate panel inline; keep the cookie — change-password endpoint
        // re-issues it after a successful rotation.
        $("rotate-form").hidden = false;
        form.hidden = true;
        $("rotate-current").focus();
        return;
      }
      // Otherwise jump straight to the dashboard.
      window.location.href = "/";
    } catch (ex) {
      showError(ex && ex.message ? ex.message : "Giriş başarısız");
    } finally {
      submit.disabled = false;
      submit.classList.remove("is-loading");
    }
  });

  // ---- First-login password rotation -----------------------------------
  const rotateBtn = $("login-rotate");
  if (rotateBtn) {
    rotateBtn.addEventListener("click", async (e) => {
      e.preventDefault();
      // Trigger the must_change_password path by attempting login with the
      // current credentials; if we're already past login, show the rotate
      // form instead.
      const rotateForm = $("rotate-form");
      const loginForm = $("login-form");
      if (!rotateForm.hidden) return;
      rotateForm.hidden = false;
      loginForm.hidden = true;
      $("rotate-current").focus();
    });
  }
  const rotateForm = $("rotate-form");
  if (rotateForm) {
    // "atla" — skip the password rotation; the user is happy with the
    // existing credentials. The must_change_password flag stays set
    // (system cleanliness, not a security gate) but the user can use
    // the dashboard as normal.
    const skip = $("rotate-skip");
    if (skip) {
      skip.addEventListener("click", () => {
        window.location.href = "/";
      });
    }
    rotateForm.addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = $("rotate-error");
      err.hidden = true;
      err.textContent = "";
      const current_password = $("rotate-current").value;
      const new_password = $("rotate-new").value;
      const new_password2 = $("rotate-new2").value;
      if (new_password !== new_password2) {
        err.textContent = "Yeni parolalar eşleşmiyor.";
        err.hidden = false;
        return;
      }
      if (new_password.length < 6) {
        err.textContent = "Yeni parola en az 6 karakter olmalı.";
        err.hidden = false;
        return;
      }
      try {
        // change-password requires a valid session; user just signed in so
        // the cookie is in place.
        const r = await fetch("/api/v1/auth/change-password", {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ current_password, new_password }),
        });
        if (!r.ok) {
          const data = await r.json().catch(() => null);
          err.textContent = "Mevcut parola hatalı / current password wrong. Henüz değiştirmediyseniz mevcut parola 'admin' olabilir.";
          err.hidden = false;
          return;
        }
        // change-password deletes the cookie. Send the user back to login.
        window.location.href = "/login.html?rotated=1";
      } catch (ex) {
        err.textContent = ex && ex.message ? ex.message : "değiştirilemedi";
        err.hidden = false;
      }
    });
  }
})();
