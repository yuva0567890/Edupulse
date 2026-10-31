/* EduPulse admin dashboard */
(function () {
  var E = window.EP, C = E.C, period = 7;
  var I = E.I18N;

  function drawStats(s) {
    var none = !s.total;
    document.getElementById('empty').style.display = none ? 'block' : 'none';
    document.getElementById('content').style.display = none ? 'none' : 'block';
    if (none) return;
    var v = { total: s.total, academics: s.categories.Academics, hostel: s.categories.Hostel, others: s.categories.Others,
              negative_count: s.negative_count, positive: s.counts.Positive, neutral: s.counts.Neutral, high_priority: s.high_priority, critical_priority: s.critical_priority, open_total: s.issues.open_total, resolved_total: s.issues.resolved_total };
    document.querySelectorAll('[data-k]').forEach(function (el) { E.counter(el, v[el.dataset.k] || 0); });
    document.getElementById('sub-open').textContent = s.issues.in_progress + ' in progress';
    document.getElementById('sub-neg').textContent = s.negative_pct + '% of all feedback';
    document.getElementById('sub-pos').textContent = s.positive_pct + '%'; document.getElementById('sub-neu').textContent = s.neutral_pct + '%';
    var c = s.counts || {};
    E.make('c-sent', { type: 'doughnut', data: { labels: ['Positive', 'Neutral', 'Negative'].map(function (k) { return I[k] || k; }),
      datasets: [{ data: [c.Positive, c.Neutral, c.Negative], backgroundColor: [C.pos, C.neu, C.neg], borderWidth: 0 }] },
      options: { cutout: '65%', plugins: { legend: { position: 'bottom' } } } });
    E.make('c-cat', { type: 'doughnut', data: { labels: ['Academics', 'Hostel', 'Others'],
      datasets: [{ data: [s.categories.Academics, s.categories.Hostel, s.categories.Others], backgroundColor: [C.acad, C.host, C.oth], borderWidth: 0 }] },
      options: { cutout: '60%', plugins: { legend: { position: 'bottom' } } } });
    var pd = s.priority_distribution;
    E.make('c-prio', { type: 'bar', data: { labels: ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'], datasets: [{ data: [pd.LOW, pd.MEDIUM, pd.HIGH, pd.CRITICAL],
      backgroundColor: [C.low, C.med, C.high, C.crit], borderRadius: 8 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
    var lb = s.language_buckets, ln = Object.keys(lb);
    E.make('c-lang', { type: 'pie', data: { labels: ln, datasets: [{ data: ln.map(function (k) { return lb[k]; }), backgroundColor: [C.acad, C.pri2, C.host, C.acc], borderWidth: 0 }] },
      options: { plugins: { legend: { position: 'bottom' } } } });
    var cs = s.category_sentiment, cats = ['Academics', 'Hostel', 'Others'];
    E.make('c-catsent', { type: 'bar', data: { labels: cats, datasets: ['Positive', 'Neutral', 'Negative'].map(function (k, i) {
      return { label: I[k] || k, data: cats.map(function (c2) { return (cs[c2] || {})[k] || 0; }), backgroundColor: [C.pos, C.neu, C.neg][i], borderRadius: 4 }; }) },
      options: { plugins: { legend: { position: 'bottom' } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
    var cp = s.category_priority, lv = ['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'], lc = [C.low, C.med, C.high, C.crit];
    E.make('c-catprio', { type: 'bar', data: { labels: cats, datasets: lv.map(function (l, i) {
      return { label: l, data: cats.map(function (c2) { return (cp[c2] || {})[l] || 0; }), backgroundColor: lc[i], borderRadius: 4 }; }) },
      options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } } });
    var lcm = s.language_category, lnames = Object.keys(lcm);
    E.make('c-langcat', { type: 'bar', data: { labels: lnames, datasets: cats.map(function (c2, i) {
      return { label: c2, data: lnames.map(function (l) { return (lcm[l] || {})[c2] || 0; }), backgroundColor: [C.acad, C.host, C.oth][i], borderRadius: 4 }; }) },
      options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } } });
    var d = s.departments.slice(0, 12);
    E.make('c-dept', { type: 'bar', data: { labels: d.map(function (x) { return x.department; }), datasets: [
      { label: 'Academics', data: d.map(function (x) { return x.Academics || 0; }), backgroundColor: C.acad },
      { label: 'Hostel', data: d.map(function (x) { return x.Hostel || 0; }), backgroundColor: C.host },
      { label: 'Others', data: d.map(function (x) { return x.Others || 0; }), backgroundColor: C.oth }] },
      options: { indexAxis: 'y', plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true, beginAtZero: true, ticks: { precision: 0 } }, y: { stacked: true } } } });
  }

  function drawTrending(t) {
    var el = document.getElementById('trending');
    if (t.status !== 'ok') { E.empty(el, '📉', t.message || 'Not enough historical data to calculate a trend.'); return; }
    el.innerHTML = t.items.map(function (x) {
      var arrow = x.direction === 'up' ? '<span class="trend-up">↑ ' + x.change_pct + '%</span>' :
                  x.direction === 'down' ? '<span class="trend-down">↓ ' + Math.abs(x.change_pct) + '%</span>' :
                  x.direction === 'new' ? '<span class="trend-new">NEW</span>' : '<span class="muted">→ 0%</span>';
      return '<div class="trend-row"><span class="name">' + E.esc(E.ASP[x.aspect] || x.aspect) + ' <span class="mini muted">' + E.esc(x.category) + '</span></span>' +
             '<span class="mini muted">' + x.previous + ' → ' + x.recent + '</span>' + arrow + '</div>';
    }).join('') + '<div class="mini muted" style="margin-top:.6rem">Negative complaints, last ' + t.period_days + ' days vs previous ' + t.period_days + ' days.</div>';
  }

  function drawCritical(r) {
    var el = document.getElementById('critical');
    if (!r.alerts.length) { E.empty(el, '✅', 'No critical issues right now (threshold: priority ≥ ' + r.threshold + ').'); return; }
    el.innerHTML = r.alerts.map(function (a) {
      var rec = (a.recommendation || {})[window.EP_LANG || 'en'] || '';
      return '<div class="card alert-crit mb"><div class="head">' + E.prio('CRITICAL') + '<b>' + E.esc((E.ASP[a.aspect] || a.aspect)) + ': ' + E.esc(a.label) + '</b></div>' +
        '<div class="small" style="margin:.5rem 0">“' + E.esc(a.sample) + '”</div>' +
        '<div class="row small" style="gap:1.2rem"><span>Complaints: <b>' + a.count + '</b></span><span>Priority: <b>' + Math.round(a.score) + '/100</b></span>' +
        '<span>Category: ' + E.cat(a.category) + '</span><span>Aspect: <b>' + E.esc(a.aspect) + '</b></span><span>Status: <b>' + E.esc(a.status) + '</b></span></div>' +
        '<div class="reco esc mt small" style="margin-top:.6rem"><b>Recommended:</b> ' + E.esc(rec) + '</div></div>';
    }).join('');
  }

  function drawSimilar(r) {
    var el = document.getElementById('similar');
    if (!r.clusters.length) { E.empty(el, '🧩', 'No recurring issues yet (two or more similar complaints are needed).'); return; }
    el.innerHTML = r.clusters.slice(0, 5).map(function (c) {
      return '<div class="card mb" style="padding:1rem"><div class="row" style="gap:.5rem"><b>' + E.esc(E.ASP[c.aspect] || c.aspect) + ' — ' + E.esc(c.label) + '</b>' + E.prio(c.priority) +
        '<span class="spacer"></span><b>' + c.count + '</b><span class="muted small">similar complaints</span></div>' + E.langbar(c.languages) + '</div>';
    }).join('') + '<a class="small" href="/admin/analytics">All recurring issues →</a>';
  }

  function drawSummary(s) {
    var el = document.getElementById('summary');
    if (s.empty) { E.empty(el, '📝', s.message); return; }
    var lang = window.EP_LANG || 'en';
    el.innerHTML = '<ul class="summary" style="padding-left:1.1rem;margin:0">' + s.bullets.map(function (b) { return '<li>' + E.esc(b[lang] || b.en) + '</li>'; }).join('') + '</ul>' +
      '<div class="mini muted" style="margin-top:.7rem">Generated from stored data · ' + E.esc(s.generated_by) + '</div>';
  }

  function drawRecent(r) {
    var el = document.getElementById('recent');
    if (!r.items.length) { E.empty(el, '📭', 'No feedback found.'); return; }
    var sc = { Positive: 'b-positive', Neutral: 'b-neutral', Negative: 'b-negative' };
    el.innerHTML = '<div class="table-wrap"><table><thead><tr><th>ID</th><th>Date</th><th>Category</th><th>Feedback</th><th>Sentiment</th><th>Priority</th><th>Status</th></tr></thead><tbody>' +
      r.items.map(function (i) {
        return '<tr class="click" onclick="location.href=\'/admin/feedback/' + i.id + '\'"><td>#' + i.id + '</td><td class="small">' + i.timestamp.slice(0, 10) + '</td><td>' + E.cat(i.category) + '</td>' +
          '<td class="text"><div class="clamp">' + E.esc(i.text) + '</div></td><td>' + E.badge(sc[i.sentiment], i.sentiment) + '</td><td>' + E.prio(i.priority) + '</td><td class="small">' + E.esc(i.status || '—') + '</td></tr>';
      }).join('') + '</tbody></table></div>';
  }

  function loadPeriod() {
    ['trending', 'summary'].forEach(function (id) { E.skeleton(document.getElementById(id), 3); });
    E.get('/api/dashboard/trending', { period: period }).then(drawTrending).catch(E.fail);
    E.get('/api/dashboard/summary', { period: period }).then(drawSummary).catch(E.fail);
  }
  function load() {
    var ex = document.getElementById('export-link'); if (ex) ex.href = '/admin/feedback/export.csv' + (E.qs() ? '?' + E.qs() : '');
    ['critical', 'similar', 'recent'].forEach(function (id) { E.skeleton(document.getElementById(id), 3); });
    E.get('/api/dashboard/stats').then(drawStats).catch(E.fail);
    E.get('/api/dashboard/critical').then(drawCritical).catch(E.fail);
    E.get('/api/dashboard/similar').then(drawSimilar).catch(E.fail);
    E.get('/api/dashboard/recent').then(drawRecent).catch(E.fail);
    loadPeriod();
  }
  document.querySelectorAll('.seg button').forEach(function (b) {
    b.addEventListener('click', function () {
      document.querySelectorAll('.seg button').forEach(function (x) { x.classList.remove('on'); });
      b.classList.add('on'); period = parseInt(b.dataset.p, 10); loadPeriod();
    });
  });
  E.bindFilters(load);
  if (typeof Chart === 'undefined' && window.epToast) epToast('Chart library could not load (check internet connection).', 'error');
  load();
})();
