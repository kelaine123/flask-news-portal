'use strict';

const CATEGORY_COLOR = {
  '半導體':    { bg: '#dbeafe', border: '#2e6cf6', font: '#1e40af' },
  'IC設計':    { bg: '#ede9fe', border: '#7c3aed', font: '#5b21b6' },
  '電子製造':  { bg: '#cffafe', border: '#0891b2', font: '#155e75' },
  '伺服器':    { bg: '#d1fae5', border: '#059669', font: '#065f46' },
  '電力電子':  { bg: '#fef3c7', border: '#d97706', font: '#92400e' },
  '面板':      { bg: '#fce7f3', border: '#db2777', font: '#9d174d' },
  '封裝測試':  { bg: '#ecfccb', border: '#65a30d', font: '#3f6212' },
  '消費電子':  { bg: '#f3e8ff', border: '#9333ea', font: '#6b21a8' },
  '半導體設備':{ bg: '#fee2e2', border: '#dc2626', font: '#991b1b' },
  '記憶體':    { bg: '#ffedd5', border: '#ea580c', font: '#9a3412' },
  '雲端':      { bg: '#e0f2fe', border: '#0284c7', font: '#075985' },
  'PCB':       { bg: '#f0fdf4', border: '#16a34a', font: '#14532d' },
  'CCL':       { bg: '#fafafa', border: '#94a3b8', font: '#334155' },
};

const DEFAULT_COLOR = { bg: '#f1f5f9', border: '#64748b', font: '#334155' };

let allNodes = [], allEdges = [], network = null, selectedId = null;

function nodeColor(category, country, dimmed) {
  const c = CATEGORY_COLOR[category] || DEFAULT_COLOR;
  const alpha = dimmed ? '33' : 'ff';
  return {
    background: c.bg,
    border: c.border + (dimmed ? '55' : ''),
    highlight: { background: c.bg, border: c.border },
  };
}

function buildGraph(data) {
  allNodes = data.nodes;
  allEdges = data.edges;

  const nodes = new vis.DataSet(data.nodes.map(n => {
    const c = CATEGORY_COLOR[n.category] || DEFAULT_COLOR;
    return {
      id: n.id,
      label: n.label,
      title: `${n.label} (${n.ticker}) · ${n.category}`,
      color: { background: c.bg, border: c.border, highlight: { background: c.bg, border: c.border } },
      font: { color: c.font, size: 13, face: 'Segoe UI, PingFang TC, sans-serif' },
      borderWidth: n.country === 'TW' ? 2.5 : 1.5,
      borderDashes: n.country !== 'TW',
      shape: 'box',
      margin: 8,
      shadow: true,
    };
  }));

  const edges = new vis.DataSet(data.edges.map((e, i) => ({
    id: i,
    from: e.from,
    to: e.to,
    title: e.label,
    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
    color: { color: '#94a3b8', highlight: '#2e6cf6', opacity: 0.7 },
    width: 1.5,
    smooth: { type: 'curvedCW', roundness: 0.15 },
  })));

  const container = document.getElementById('sc-graph');
  network = new vis.Network(container, { nodes, edges }, {
    physics: {
      enabled: true,
      solver: 'forceAtlas2Based',
      forceAtlas2Based: { gravitationalConstant: -60, springLength: 120, springConstant: 0.06 },
      stabilization: { iterations: 200 },
    },
    interaction: { hover: true, tooltipDelay: 150 },
    layout: { improvedLayout: false },
  });

  network.on('click', params => {
    if (params.nodes.length) selectNode(params.nodes[0]);
    else clearDetail();
  });

  network.once('stabilized', () => network.fit({ animation: { duration: 600 } }));
}

function selectNode(id) {
  selectedId = id;
  fetch(`/api/supply-chain/company/${id}`)
    .then(r => r.json())
    .then(data => {
      showDetail(data);
      highlightConnected(id);
      highlightListItem(id);
    });
}

function highlightConnected(id) {
  const connected = new Set([id]);
  allEdges.forEach(e => {
    if (e.from === id) connected.add(e.to);
    if (e.to === id) connected.add(e.from);
  });
  network.setData({
    nodes: new vis.DataSet(allNodes.map(n => {
      const dimmed = !connected.has(n.id);
      const c = CATEGORY_COLOR[n.category] || DEFAULT_COLOR;
      return {
        id: n.id, label: n.label,
        title: `${n.label} (${n.ticker}) · ${n.category}`,
        color: {
          background: dimmed ? '#f8fafc' : c.bg,
          border: dimmed ? '#cbd5e1' : c.border,
          highlight: { background: c.bg, border: c.border },
        },
        font: { color: dimmed ? '#cbd5e1' : c.font, size: 13, face: 'Segoe UI, PingFang TC, sans-serif' },
        borderWidth: n.country === 'TW' ? 2.5 : 1.5,
        borderDashes: n.country !== 'TW',
        shape: 'box', margin: 8, shadow: !dimmed,
        opacity: dimmed ? 0.3 : 1,
      };
    })),
    edges: new vis.DataSet(allEdges.map((e, i) => {
      const active = e.from === id || e.to === id;
      return {
        id: i, from: e.from, to: e.to, title: e.label,
        arrows: { to: { enabled: true, scaleFactor: 0.7 } },
        color: { color: active ? '#2e6cf6' : '#e2e8f0', opacity: active ? 1 : 0.2 },
        width: active ? 2.5 : 1,
        smooth: { type: 'curvedCW', roundness: 0.15 },
      };
    })),
  });
}

function clearDetail() {
  selectedId = null;
  document.getElementById('sc-detail').style.display = 'none';
  document.querySelectorAll('.sc-company-list li').forEach(li => li.classList.remove('active'));
  buildGraph({ nodes: allNodes, edges: allEdges });
}

function showDetail(data) {
  const c = data.company || data;
  document.getElementById('detail-name').textContent = c.name;
  document.getElementById('detail-ticker').textContent = c.ticker;
  document.getElementById('detail-category').textContent = c.category;
  document.getElementById('detail-country').textContent = c.country;

  const up = document.getElementById('detail-upstream');
  up.innerHTML = data.upstream.length
    ? data.upstream.map(r =>
        `<li><span class="rel-company">${r.name}</span><span class="rel-product">${r.product}</span></li>`
      ).join('')
    : '<li class="rel-empty">無資料</li>';

  const down = document.getElementById('detail-downstream');
  down.innerHTML = data.downstream.length
    ? data.downstream.map(r =>
        `<li><span class="rel-company">${r.name}</span><span class="rel-product">${r.product}</span></li>`
      ).join('')
    : '<li class="rel-empty">無資料</li>';

  document.getElementById('sc-detail').style.display = 'block';
}

function highlightListItem(id) {
  document.querySelectorAll('.sc-company-list li').forEach(li => {
    li.classList.toggle('active', parseInt(li.dataset.id) === id);
  });
}

function renderList(companies) {
  const ul = document.getElementById('company-list');
  ul.innerHTML = companies.map(c => `
    <li data-id="${c.id}" data-country="${c.country}" title="${c.category}">
      <span class="cl-name">${c.name}</span>
      <span class="cl-ticker">${c.ticker}</span>
      <span class="cl-flag">${flagEmoji(c.country)}</span>
    </li>
  `).join('');
  ul.querySelectorAll('li').forEach(li => {
    li.addEventListener('click', () => {
      const id = parseInt(li.dataset.id);
      selectNode(id);
      network.focus(id, { scale: 1.2, animation: { duration: 500 } });
    });
  });
}

function flagEmoji(country) {
  const flags = { TW: '🇹🇼', US: '🇺🇸', KR: '🇰🇷', NL: '🇳🇱' };
  return flags[country] || country;
}

function applyFilters() {
  const q = document.getElementById('sc-search').value.toLowerCase();
  const activeCountry = document.querySelector('#country-filters .sc-chip.active').dataset.country;
  document.querySelectorAll('#company-list li').forEach(li => {
    const name = li.querySelector('.cl-name').textContent.toLowerCase();
    const country = li.dataset.country;
    const matchQ = !q || name.includes(q);
    const matchC = activeCountry === 'all' || country === activeCountry;
    li.style.display = matchQ && matchC ? '' : 'none';
  });
}

// ── Bootstrap ──────────────────────────────────────────────────────────────

Promise.all([
  fetch('/api/supply-chain/graph').then(r => r.json()),
  fetch('/api/supply-chain/companies').then(r => r.json()),
  fetch('/api/supply-chain/stats').then(r => r.json()),
]).then(([graph, companies, stats]) => {
  document.getElementById('stat-tw').textContent = stats.tw_companies;
  document.getElementById('stat-companies').textContent = stats.companies;
  document.getElementById('stat-rels').textContent = stats.relationships;

  buildGraph(graph);
  renderList(companies);
});

document.getElementById('sc-search').addEventListener('input', applyFilters);

document.getElementById('country-filters').addEventListener('click', e => {
  const chip = e.target.closest('.sc-chip');
  if (!chip) return;
  document.querySelectorAll('#country-filters .sc-chip').forEach(c => c.classList.remove('active'));
  chip.classList.add('active');
  applyFilters();
});

document.getElementById('detail-close').addEventListener('click', clearDetail);
