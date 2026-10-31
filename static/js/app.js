/* EduPulse - shared UI behaviour: toasts, theme, feedback form helpers */
(function () {
  function toast(msg, kind) {
    var box = document.getElementById('toasts'); if (!box) return;
    var d = document.createElement('div'); d.className = 'toast ' + (kind === 'message' ? 'info' : (kind || 'info'));
    d.textContent = msg; box.appendChild(d);
    setTimeout(function () { d.style.opacity = '0'; d.style.transition = 'opacity .4s'; setTimeout(function () { d.remove(); }, 400); }, 4500);
  }
  window.epToast = toast;

  try {
    var raw = document.getElementById('flashes');
    (JSON.parse(raw ? raw.textContent : '[]') || []).forEach(function (m) { toast(m[1], m[0]); });
  } catch (e) {}

  var tt = document.getElementById('theme-toggle');
  if (tt) tt.addEventListener('click', function () {
    var cur = document.documentElement.getAttribute('data-theme') === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', cur);
    try { localStorage.setItem('ep-theme', cur); } catch (e) {}
    if (window.epRedraw) window.epRedraw();
  });

  /* feedback form */
  var form = document.getElementById('fb-form');
  if (form) {
    var ta = document.getElementById('text'), cc = document.getElementById('cc');
    function upd() { if (cc) cc.textContent = ta.value.length + ' / 5000'; }
    ta.addEventListener('input', upd); upd();
    document.querySelectorAll('[data-example]').forEach(function (b) {
      b.addEventListener('click', function () { ta.value = b.getAttribute('data-example'); upd(); ta.focus(); });
    });
    form.addEventListener('submit', function (e) {
      if (ta.value.trim().length < 3) {
        e.preventDefault(); toast('Please write at least a few words of feedback.', 'error'); ta.focus(); return;
      }
      var btn = document.getElementById('fb-submit'); btn.classList.add('loading');
      setTimeout(function () { btn.disabled = true; }, 0);
    });
  }

  /* authentication forms: password visibility, strength meter, client-side validation, loading state */
  document.querySelectorAll('.pw-toggle').forEach(function (b) {
    b.addEventListener('click', function () {
      var i = document.getElementById(b.getAttribute('data-toggle'));
      if (!i) return;
      var show = i.type === 'password'; i.type = show ? 'text' : 'password';
      b.textContent = show ? '🙈' : '👁'; b.setAttribute('aria-label', show ? 'Hide password' : 'Show password');
    });
  });
  var af = document.getElementById('auth-form');
  if (af) {
    var pw = document.getElementById('password'), meter = document.getElementById('pw-meter');
    function err(name, msg) {
      var el = af.querySelector('[data-err="' + name + '"]'), inp = af.querySelector('[name="' + name + '"]');
      if (el) el.textContent = msg || ''; if (inp) inp.classList.toggle('invalid', !!msg);
    }
    if (pw && meter) pw.addEventListener('input', function () {
      var v = pw.value, sc = 0; if (v.length >= 8) sc++; if (/[A-Z]/.test(v) && /[a-z]/.test(v)) sc++; if (/\d/.test(v)) sc++; if (/[^A-Za-z0-9]/.test(v)) sc++;
      meter.style.width = (v ? 25 * Math.max(sc, 1) : 0) + '%'; meter.style.background = ['', '#e5484d', '#d99a0b', '#10b9a5', '#10a37f'][Math.max(sc, 1)];
    });
    af.addEventListener('submit', function (e) {
      var ok = true;
      if (af.querySelector('[name="email"]')) {   // sign-up form
        var u = af.username.value.trim(), em = af.email.value.trim(), min = parseInt(af.getAttribute('data-min') || '8', 10);
        err('username', /^[A-Za-z0-9][A-Za-z0-9._-]{2,39}$/.test(u) ? '' : 'Use 3-40 letters, numbers, dots, dashes or underscores.');
        err('email', /^[^@\s]+@[^@\s]+\.[A-Za-z]{2,}$/.test(em) ? '' : 'Enter a valid email address.');
        err('password', af.password.value.length >= min ? '' : 'Password must be at least ' + min + ' characters.');
        err('confirm', af.confirm.value && af.confirm.value === af.password.value ? '' : 'Passwords do not match.');
        ok = !af.querySelector('.invalid');
      } else if (!af.identifier.value.trim() || !af.password.value) { ok = false; toast('Enter your email/username and password.', 'error'); }
      if (!ok) { e.preventDefault(); return; }
      var btn = document.getElementById('auth-submit'); btn.classList.add('loading'); setTimeout(function () { btn.disabled = true; }, 0);
    });
  }
})();
