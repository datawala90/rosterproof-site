function loadGapMap(initFn) {
  // Defer the ~290KB map runtime until the map scrolls near the viewport
  let loaded = false;
  function load() {
    if (loaded) return; loaded = true;
    const add = (src) => new Promise(res => {
      const sc = document.createElement('script'); sc.src = src; sc.onload = res;
      document.body.appendChild(sc);
    });
    add('/assets/vendor/d3.v7.min.js')
      .then(() => add('/assets/vendor/topojson-client.min.js'))
      .then(initFn);
  }
  const el = document.getElementById('gapmap');
  if (!el || !('IntersectionObserver' in window)) { load(); return; }
  const io = new IntersectionObserver(es => {
    if (es.some(e => e.isIntersecting)) { io.disconnect(); load(); }
  }, {rootMargin: '600px'});
  io.observe(el);
}
loadGapMap(function () {
  const FIPS = {'01':'AL','02':'AK','04':'AZ','05':'AR','06':'CA','08':'CO','09':'CT','10':'DE',
    '11':'DC','12':'FL','13':'GA','15':'HI','16':'ID','17':'IL','18':'IN','19':'IA','20':'KS',
    '21':'KY','22':'LA','23':'ME','24':'MD','25':'MA','26':'MI','27':'MN','28':'MS','29':'MO',
    '30':'MT','31':'NE','32':'NV','33':'NH','34':'NJ','35':'NM','36':'NY','37':'NC','38':'ND',
    '39':'OH','40':'OK','41':'OR','42':'PA','44':'RI','45':'SC','46':'SD','47':'TN','48':'TX',
    '49':'UT','50':'VT','51':'VA','53':'WA','54':'WV','55':'WI','56':'WY'};
  const NAMES = {AL:'Alabama',AK:'Alaska',AZ:'Arizona',AR:'Arkansas',CA:'California',CO:'Colorado',
    CT:'Connecticut',DE:'Delaware',DC:'District of Columbia',FL:'Florida',GA:'Georgia',HI:'Hawaii',
    ID:'Idaho',IL:'Illinois',IN:'Indiana',IA:'Iowa',KS:'Kansas',KY:'Kentucky',LA:'Louisiana',
    ME:'Maine',MD:'Maryland',MA:'Massachusetts',MI:'Michigan',MN:'Minnesota',MS:'Mississippi',
    MO:'Missouri',MT:'Montana',NE:'Nebraska',NV:'Nevada',NH:'New Hampshire',NJ:'New Jersey',
    NM:'New Mexico',NY:'New York',NC:'North Carolina',ND:'North Dakota',OH:'Ohio',OK:'Oklahoma',
    OR:'Oregon',PA:'Pennsylvania',RI:'Rhode Island',SC:'South Carolina',SD:'South Dakota',
    TN:'Tennessee',TX:'Texas',UT:'Utah',VT:'Vermont',VA:'Virginia',WA:'Washington',
    WV:'West Virginia',WI:'Wisconsin',WY:'Wyoming'};
  const FMT = {CSV:'CSV',TSV:'CSV',XLSX:'Excel',XLS:'Excel',PDF:'PDF',JSON:'JSON endpoint',HTML_TABLE:'Portal'};
  const RAMP = ['#14384c','#1d5560','#2a7873','#46a58f','#7fd4c8'];
  const BRIGHT = ['#1d5560','#2a7873','#46a58f','#7fd4c8','#a5e6dc'];  // one step up
  const INK = '#f2f7ff';   // one ink for all labels; the dark halo (CSS) carries contrast on every fill
  const GRAY = '#2a3350';
  const SMALL = ['CT','NJ','DE','MD','DC','MA','RI','NH','VT'];   // leader-line cluster

  const step = g => g >= 80 ? 4 : g >= 60 ? 3 : g >= 40 ? 2 : g >= 20 ? 1 : 0;
  const isMobile = () => window.matchMedia('(max-width:640px)').matches;

  Promise.all([
    fetch('stats.json').then(r => r.json()),
    fetch('/assets/vendor/states-albers-10m.json').then(r => r.json())
  ]).then(([stats, topo]) => {
    const gaps = {};
    stats.state_gaps.forEach(g => gaps[g.state] = g);
    const top10 = stats.state_gaps.slice(0, 10).map(g => g.state);

    const svg = d3.select('#gapmap');
    const path = d3.geoPath();
    const states = topojson.feature(topo, topo.objects.states).features;
    const gMap = svg.append('g');
    const gLead = svg.append('g');
    const gLab = svg.append('g');
    const tip = document.getElementById('map-tip');
    const card = document.querySelector('.mapcard');
    let focused = null;

    const meta = {};   // postal -> {d: gapdata|null, centroid, stepIdx, path, label}

    states.forEach(f => {
      const postal = FIPS[f.id];
      if (!postal) return;
      const g = gaps[postal] || null;
      const idx = g ? step(g.gap_pct) : -1;
      meta[postal] = { d: g, stepIdx: idx, centroid: path.centroid(f) };
      meta[postal].path = gMap.append('path')
        .attr('d', path(f))
        .attr('class', 'gm-state')
        .attr('fill', g ? RAMP[idx] : GRAY)
        .on('mouseenter', () => { if (!isMobile()) focus(postal); })
        .on('mouseleave', () => { if (!isMobile()) blur(); })
        .on('click', ev => { ev.stopPropagation();
          if (focused === postal) blur(); else focus(postal); });
    });

    // resting labels: loaded, non-small states (mobile: top-10 only)
    const smallLoaded = SMALL.filter(p => meta[p] && meta[p].d);
    Object.keys(meta).forEach(postal => {
      const m = meta[postal];
      if (!m.d || SMALL.includes(postal)) return;
      m.label = gLab.append('text')
        .attr('class', 'gm-label')
        .attr('transform', `translate(${m.centroid[0]},${m.centroid[1]})`)
        .attr('text-anchor', 'middle').attr('dy', '0.35em')
        .attr('fill', INK)
        .text(m.d.gap_pct.toFixed(1));
    });

    // small NE cluster: leader lines to a right-edge label column
    smallLoaded.sort((a, b) => meta[a].centroid[1] - meta[b].centroid[1]);
    smallLoaded.forEach((postal, i) => {
      const m = meta[postal];
      const lx = 1000, ly = 120 + i * 30;
      if (!isMobile()) {
        gLead.append('polyline').attr('class', 'gm-leader')
          .attr('points', `${m.centroid[0]},${m.centroid[1]} ${lx - 8},${ly}`);
      }
      m.labelXY = [lx, ly];
      m.label = gLab.append('text')
        .attr('class', 'gm-label')
        .attr('transform', `translate(${lx},${ly})`)
        .attr('text-anchor', 'start').attr('dy', '0.35em')
        .attr('fill', '#c7d2ea')
        .style('display', isMobile() ? 'none' : null)
        .text(`${postal} ${m.d.gap_pct.toFixed(1)}`)
        .style('cursor', 'pointer')
        .style('pointer-events', 'all')
        .on('mouseenter', () => { if (!isMobile()) focus(postal); })
        .on('mouseleave', () => { if (!isMobile()) blur(); });
    });

    function focus(postal) {
      const m = meta[postal];
      if (!m || !m.d) { blur(); return; }
      blur(false);
      focused = postal;
      m.path.attr('fill', BRIGHT[m.stepIdx])
            .attr('stroke', '#cfeee8').attr('stroke-width', 1.5).raise();
      gLab.selectAll('text').transition().duration(150).ease(d3.easeCubicOut)
          .style('opacity', 0.4);
      if (m.label) {
        const [cx, cy] = m.labelXY || m.centroid;
        m.label.raise().transition().duration(150).ease(d3.easeCubicOut)
          .style('opacity', 1).style('font-weight', 700)
          .attr('transform', `translate(${cx},${cy}) scale(2)`);
      }
      const fmt = FMT[m.d.source_format] || m.d.source_format || '';
      tip.innerHTML = `<b>${NAMES[postal]}</b><br>${m.d.gap_pct.toFixed(1)}% not on the federal LEIE<br>` +
        `${m.d.active_records.toLocaleString('en-US')} active exclusions` +
        (fmt ? `<br><span class="fmtchip">${fmt}</span>` : '');
      tip.style.display = 'block';
      const r = card.getBoundingClientRect();
      const pt = m.labelXY || m.centroid;
      const sx = r.width / 1085;
      tip.style.left = Math.min(pt[0] * sx + 24, r.width - 240) + 'px';
      tip.style.top = Math.max(pt[1] * sx * (620 / 620) - 10, 8) + 'px';
    }

    function blur(hideTip = true) {
      if (focused) {
        const m = meta[focused];
        m.path.attr('fill', RAMP[m.stepIdx]).attr('stroke', null).attr('stroke-width', null);
        if (m.label) {
          const [cx, cy] = m.labelXY || m.centroid;
          m.label.transition().duration(150).ease(d3.easeCubicOut)
            .style('font-weight', null)
            .attr('transform', `translate(${cx},${cy}) scale(1)`);
        }
        focused = null;
      }
      gLab.selectAll('text').transition().duration(150).ease(d3.easeCubicOut).style('opacity', 1);
      if (hideTip) tip.style.display = 'none';
    }
    document.addEventListener('click', () => { if (focused) blur(); });

    // legend
    const legend = document.getElementById('gm-legend');
    const bands = ['under 20%', '20–40%', '40–60%', '60–80%', '80%+'];
    legend.innerHTML = bands.map((b, i) =>
      `<span><span class="sw" style="background:${RAMP[i]}"></span>${b}</span>`).join('') +
      `<span><span class="sw" style="background:${GRAY}"></span>no state list published, or not yet loaded</span>` +
      `<span style="margin-left:auto">gap % = share of that state's active exclusions absent from the federal LEIE</span>`;
  }).catch(e => console.error('map failed', e));
});
