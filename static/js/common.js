/* EduPulse shared helpers for dashboard / analytics pages */
window.EP = (function () {
  var charts = {};
  var C = { pos: '#10a37f', neu: '#d99a0b', neg: '#e5484d', pri: '#5b4cf0', pri2: '#8b5cf6', acc: '#10b9a5',
            low: '#10a37f', med: '#d99a0b', high: '#f06a1d', crit: '#d6249f',
            acad: '#3b5bdb', host: '#f76707', oth: '#12b886' };
  var form = document.getElementById('filters');
  var I18N = window.EP_I18N || {}, ASP = window.EP_ASPECTS || {};

  function qs(extra) {
    var p = new URLSearchParams();
    if (form) new FormData(form).forEach(function (v, k) { if (v) p.append(k, v); });
    Object.keys(extra || {}).forEach(function (k) { p.set(k, extra[k]); });
    return p.toString();
  }
  function get(u, extra) {
    var q = qs(extra);
    return fetch(u + (q ? '?' + q : ''), { credentials: 'same-origin' }).then(function (r) {
      if (r.status === 401) { location.href = '/admin/login'; throw new Error('auth'); }
      if (!r.ok) throw new Error('HTTP ' + r.status);
      return r.json();
    });
  }
  function esc(s) { return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
    return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function txt() { return getComputedStyle(document.documentElement).getPropertyValue('--muted').trim() || '#6b7194'; }
  function make(id, cfg) {
    var el = document.getElementById(id);
    if (typeof Chart === 'undefined' || !el) return;
    if (charts[id]) charts[id].destroy();
    cfg.options = cfg.options || {}; cfg.options.responsive = true; cfg.options.maintainAspectRatio = false;
    Chart.defaults.color = txt(); Chart.defaults.font.family = 'Inter, "Noto Sans Tamil", "Noto Sans Devanagari", sans-serif';
    charts[id] = new Chart(el, cfg);
  }
  function counter(el, to, suffix) {
    var start = null, dec = String(to).indexOf('.') >= 0 ? 1 : 0;
    function step(ts) { if (!start) start = ts; var p = Math.min((ts - start) / 700, 1), v = to * (1 - Math.pow(1 - p, 3));
      el.textContent = v.toFixed(dec) + (suffix || ''); if (p < 1) requestAnimationFrame(step); }
    requestAnimationFrame(step);
  }
  function shade(v, max, rgb) { var a = max ? 0.12 + 0.88 * v / max : 0.1; return 'rgba(' + rgb + ',' + a.toFixed(2) + ')'; }
  function skeleton(el, n) { var h = ''; for (var i = 0; i < (n || 3); i++) h += '<div class="skeleton" style="height:18px;margin:.6rem 0"></div>'; el.innerHTML = h; }
  function empty(el, icon, msg) { el.innerHTML = '<div class="empty" style="padding:1.6rem .5rem"><div class="big" style="font-size:2rem">' + icon + '</div><div>' + esc(msg) + '</div></div>'; }
  function badge(cls, label) { return '<span class="badge ' + cls + '">' + esc(label) + '</span>'; }
  function prio(l) { return badge('p-' + l.toLowerCase() + (l === 'CRITICAL' ? ' pulse' : ''), l); }
  function cat(c) { return badge('cat-' + c.toLowerCase(), c); }
  function langbar(l) {
    var tot = 0, cols = { Tamil: C.acad, English: C.pri2, Hindi: C.host, Mixed: C.acc }, h = '';
    Object.keys(l).forEach(function (k) { tot += l[k]; });
    if (!tot) return '';
    h = '<div class="langbar">';
    Object.keys(l).forEach(function (k) { if (l[k]) h += '<i style="width:' + (100 * l[k] / tot) + '%;background:' + cols[k] + '" title="' + k + ': ' + l[k] + '"></i>'; });
    h += '</div><div class="mini muted" style="margin-top:.3rem">';
    Object.keys(l).forEach(function (k) { h += k + ': <b>' + l[k] + '</b> &nbsp; '; });
    return h + '</div>';
  }
  function bindFilters(load) {
    if (!form) return;
    var apply = document.getElementById('apply'), reset = document.getElementById('reset');
    if (apply) apply.addEventListener('click', load);
    form.querySelectorAll('select,input').forEach(function (el) { el.addEventListener('change', load); });
    if (reset) reset.addEventListener('click', function () { form.reset(); load(); });
    window.epRedraw = load;
  }
  function fail(e) { if (e.message !== 'auth' && window.epToast) epToast('Could not load data: ' + e.message, 'error'); }
  return { C: C, qs: qs, get: get, make: make, counter: counter, shade: shade, esc: esc, skeleton: skeleton, empty: empty,
           badge: badge, prio: prio, cat: cat, langbar: langbar, bindFilters: bindFilters, fail: fail, I18N: I18N, ASP: ASP };
})();
