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

let allNodes = [], allEdges = [];
let nodesDS = null, edgesDS = null, network = null;

// ── Node / Edge builders ───────────────────────────────────────────────────

function makeNode(n, dimmed = false) {
  const c = CATEGORY_COLOR[n.category] || DEFAULT_COLOR;
  return {
    id: n.id,
    label: n.label,
    title: `${n.label} (${n.ticker}) · ${n.category}`,
    color: {
      background: dimmed ? '#f1f5f9' : c.bg,
      border:     dimmed ? '#cbd5e1' : c.border,
      highlight:  { background: c.bg, border: c.border },
    },
    font: { color: dimmed ? '#cbd5e1' : c.font, size: 13, face: 'Segoe UI, PingFang TC, sans-serif' },
    borderWidth:  n.country === 'TW' ? 2.5 : 1.5,
    borderDashes: n.country !== 'TW',
    shape: 'box',
    margin: 8,
    shadow: !dimmed,
    opacity: dimmed ? 0.25 : 1,
  };
}

function makeEdge(e, i, active = false) {
  return {
    id: i, from: e.from, to: e.to, title: e.label,
    arrows: { to: { enabled: true, scaleFactor: 0.7 } },
    color: { color: active ? '#2e6cf6' : '#94a3b8', opacity: active ? 1 : 0.5 },
    width: active ? 2.5 : 1.2,
    smooth: { type: 'curvedCW', roundness: 0.15 },
  };
}

// ── Graph ──────────────────────────────────────────────────────────────────

function buildGraph(data) {
  allNodes = data.nodes;
  allEdges = data.edges;

  nodesDS = new vis.DataSet(allNodes.map(n => makeNode(n)));
  edgesDS = new vis.DataSet(allEdges.map((e, i) => makeEdge(e, i)));

  const container = document.getElementById('sc-graph');
  network = new vis.Network(
    container,
    { nodes: nodesDS, edges: edgesDS },
    {
      physics: {
        enabled: true,
        solver: 'forceAtlas2Based',
        forceAtlas2Based: { gravitationalConstant: -60, springLength: 130, springConstant: 0.06 },
        stabilization: { iterations: 200 },
      },
      interaction: { hover: true, tooltipDelay: 150 },
      layout: { improvedLayout: false },
    }
  );

  network.on('click', params => {
    if (params.nodes.length) selectNode(params.nodes[0]);
    else clearDetail();
  });

  network.once('stabilized', () => network.fit({ animation: { duration: 600 } }));
}

// ── Selection & highlight ──────────────────────────────────────────────────

function selectNode(id) {
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
    if (e.to === id)   connected.add(e.from);
  });
  // Update existing DataSets — no network rebuild, click event stays intact
  nodesDS.update(allNodes.map(n => makeNode(n, !connected.has(n.id))));
  edgesDS.update(allEdges.map((e, i) => makeEdge(e, i, e.from === id || e.to === id)));
}

function clearDetail() {
  document.getElementById('sc-detail').style.display = 'none';
  document.querySelectorAll('.sc-company-list li').forEach(li => li.classList.remove('active'));
  nodesDS.update(allNodes.map(n => makeNode(n)));
  edgesDS.update(allEdges.map((e, i) => makeEdge(e, i)));
}

// ── Detail panel ───────────────────────────────────────────────────────────

function showDetail(data) {
  document.getElementById('detail-name').textContent     = data.name;
  document.getElementById('detail-ticker').textContent   = data.ticker;
  document.getElementById('detail-category').textContent = data.category;
  document.getElementById('detail-country').textContent  = data.country;

  document.getElementById('detail-upstream').innerHTML = data.upstream.length
    ? data.upstream.map(r =>
        `<li><span class="rel-company">${r.name}</span><span class="rel-product">${r.product}</span></li>`
      ).join('')
    : '<li class="rel-empty">無資料</li>';

  document.getElementById('detail-downstream').innerHTML = data.downstream.length
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
  const active = document.querySelector('.sc-company-list li.active');
  if (active) active.scrollIntoView({ block: 'nearest' });
}

// ── Company list ───────────────────────────────────────────────────────────

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
      network.focus(id, { scale: 1.3, animation: { duration: 500 } });
    });
  });
}

function flagEmoji(c) {
  return { TW: '🇹🇼', US: '🇺🇸', KR: '🇰🇷', NL: '🇳🇱' }[c] || c;
}

function applyFilters() {
  const q       = document.getElementById('sc-search').value.toLowerCase();
  const country = document.querySelector('#country-filters .sc-chip.active').dataset.country;
  document.querySelectorAll('#company-list li').forEach(li => {
    const name    = li.querySelector('.cl-name').textContent.toLowerCase();
    const matchQ  = !q || name.includes(q);
    const matchC  = country === 'all' || li.dataset.country === country;
    li.style.display = matchQ && matchC ? '' : 'none';
  });
}

// ── Bootstrap ──────────────────────────────────────────────────────────────

Promise.all([
  fetch('/api/supply-chain/graph').then(r => r.json()),
  fetch('/api/supply-chain/companies').then(r => r.json()),
  fetch('/api/supply-chain/stats').then(r => r.json()),
]).then(([graph, companies, stats]) => {
  document.getElementById('stat-tw').textContent        = stats.tw_companies;
  document.getElementById('stat-companies').textContent = stats.companies;
  document.getElementById('stat-rels').textContent      = stats.relationships;

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
