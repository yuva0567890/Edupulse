/* EduPulse analytics page: aspects, heatmap, languages, recurring issues */
(function () {
  var E = window.EP, C = E.C, I = E.I18N;
  var catCol = { Academics: C.acad, Hostel: C.host, Others: C.oth };

  function drawAspects(a) {
    var names = Object.keys(a.distribution);
    document.getElementById('a-empty').style.display = names.some(function (n) { return a.distribution[n]; }) ? 'none' : 'block';
    E.make('c-aspect', { type: 'bar', data: { labels: names.map(function (n) { return E.ASP[n] || n; }), datasets: [{ data: names.map(function (n) { return a.distribution[n]; }),
      backgroundColor: names.map(function (n) { return catCol[a.categories[n]] || C.pri; }), borderRadius: 8 }] },
      options: { plugins: { legend: { display: false } }, scales: { y: { beginAtZero: true, ticks: { precision: 0 } } } } });
    var h = a.heatmap, max = 0, sents = ['Positive', 'Neutral', 'Negative'], rgb = { Positive: '16,163,127', Neutral: '217,154,11', Negative: '229,72,77' };
    names.forEach(function (n) { sents.forEach(function (s) { max = Math.max(max, h[n][s]); }); });
    var html = '<div class="heat" style="grid-template-columns:150px repeat(3,1fr)"><div></div>' + sents.map(function (s) { return '<div class="hd">' + (I[s] || s) + '</div>'; }).join('');
    names.forEach(function (n) { html += '<div class="hd" style="justify-items:start;text-align:left">' + E.esc(E.ASP[n] || n) + '</div>';
      sents.forEach(function (s) { var v = h[n][s]; html += '<div class="cell" style="background:' + E.shade(v, max, rgb[s]) + '">' + v + '</div>'; }); });
    document.getElementById('heatmap').innerHTML = html + '</div>';
  }
  function drawLangs(l) {
    var names = Object.keys(l.distribution);
    E.make('c-langsent', { type: 'bar', data: { labels: names, datasets: ['Positive', 'Neutral', 'Negative'].map(function (s, i) {
      return { label: I[s] || s, data: names.map(function (n) { return l.by_sentiment[n][s]; }), backgroundColor: [C.pos, C.neu, C.neg][i], borderRadius: 4 }; }) },
      options: { plugins: { legend: { position: 'bottom' } }, scales: { x: { stacked: true }, y: { stacked: true, beginAtZero: true, ticks: { precision: 0 } } } } });
  }
  function drawComplaints(s) {
    var rc = s.recurring_complaints || [];
    E.make('c-complaints', { type: 'bar', data: { labels: rc.map(function (x) { return (E.ASP[x.aspect] || x.aspect) + ' — ' + x.term; }),
      datasets: [{ data: rc.map(function (x) { return x.count; }), backgroundColor: C.neg, borderRadius: 6 }] },
      options: { indexAxis: 'y', plugins: { legend: { display: false } }, scales: { x: { beginAtZero: true, ticks: { precision: 0 } } } } });
  }
  function drawClusters(r) {
    var el = document.getElementById('clusters');
    if (!r.clusters.length) { E.empty(el, '🧩', 'No recurring issues yet. Similar complaints are grouped once two or more students report the same problem.'); return; }
    el.innerHTML = '<div class="small muted mb">Similarity threshold: ' + r.threshold + ' (Admin → Settings). ' + r.total_clusters + ' recurring issue(s).</div>' +
      '<div class="grid g2">' + r.clusters.map(function (c) {
        return '<div class="card"><div class="row" style="gap:.5rem"><b>' + E.esc(E.ASP[c.aspect] || c.aspect) + '</b>' + E.cat(c.category) + E.prio(c.priority) + '<span class="spacer"></span><span class="big-label" style="font-size:1.5rem">' + c.count + '</span></div>' +
          '<div class="muted small">Recurring issue: <b>' + E.esc(c.label) + '</b> · priority ' + Math.round(c.score) + '/100</div>' +
          '<div class="small" style="margin:.5rem 0">“' + E.esc(c.sample) + '”</div>' + E.langbar(c.languages) +
          '<div class="mini muted" style="margin-top:.5rem">Feedback: ' + c.feedback_ids.slice(0, 8).map(function (i) { return '<a href="/admin/feedback/' + i + '">#' + i + '</a>'; }).join(', ') + (c.feedback_ids.length > 8 ? ' …' : '') + '</div></div>';
      }).join('') + '</div>';
  }
  function load() {
    E.skeleton(document.getElementById('clusters'), 4);
    E.get('/api/dashboard/aspects').then(drawAspects).catch(E.fail);
    E.get('/api/dashboard/languages').then(drawLangs).catch(E.fail);
    E.get('/api/dashboard/stats').then(drawComplaints).catch(E.fail);
    E.get('/api/dashboard/similar').then(drawClusters).catch(E.fail);
  }
  E.bindFilters(load);
  load();
})();
