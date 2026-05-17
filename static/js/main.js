const SENTIMENT_LABEL = { positive: "正面", negative: "負面", neutral: "中性" };

let allArticles = [];
let activeFilter = "all";
let activeCategory = "all";

async function fetchNews() {
  const res = await fetch("/api/news");
  if (!res.ok) throw new Error("API error");
  const data = await res.json();
  return data.articles;
}

function updateStats(articles) {
  const pos = articles.filter(a => a.sentiment === "positive").length;
  const neg = articles.filter(a => a.sentiment === "negative").length;
  const neu = articles.filter(a => a.sentiment === "neutral").length;
  const latest = articles.map(a => a.date).sort().reverse()[0] ?? "—";

  document.getElementById("stat-total").textContent    = articles.length;
  document.getElementById("stat-positive").textContent = pos;
  document.getElementById("stat-negative").textContent = neg;
  document.getElementById("stat-neutral").textContent  = neu;
  document.getElementById("stat-date").textContent     = latest;
}

function populateCategories(articles) {
  const cats = [...new Set(articles.map(a => a.category))].sort();
  const sel = document.getElementById("category-filter");
  cats.forEach(c => {
    const opt = document.createElement("option");
    opt.value = c;
    opt.textContent = c;
    sel.appendChild(opt);
  });
}

function getFilteredArticles() {
  return allArticles.filter(a => {
    const sentOk = activeFilter === "all" || a.sentiment === activeFilter;
    const catOk  = activeCategory === "all" || a.category === activeCategory;
    return sentOk && catOk;
  });
}

function renderCard(article) {
  const card = document.createElement("div");
  card.className = "card";
  card.dataset.id = article.id;
  card.innerHTML = `
    <div class="card-bar ${article.sentiment}"></div>
    <div class="card-meta">
      <div class="card-company">
        <span class="company-badge">${article.company}</span>
        <span class="ticker-badge">${article.ticker}</span>
      </div>
      <span class="sentiment-badge ${article.sentiment}">${SENTIMENT_LABEL[article.sentiment]}</span>
    </div>
    <div>
      <span class="card-category">${article.category}</span>
    </div>
    <div class="card-title">${article.title}</div>
    <div class="card-summary">${article.summary}</div>
    <div class="card-footer">
      <span class="card-date">${article.date}</span>
      <div class="card-tags">
        ${article.tags.slice(0, 3).map(t => `<span class="tag">${t}</span>`).join("")}
      </div>
    </div>
  `;
  card.addEventListener("click", () => openModal(article));
  return card;
}

function renderGrid() {
  const grid = document.getElementById("news-grid");
  grid.innerHTML = "";
  const filtered = getFilteredArticles();
  if (filtered.length === 0) {
    grid.innerHTML = '<div class="loading">沒有符合條件的文章</div>';
    return;
  }
  filtered.forEach(a => grid.appendChild(renderCard(a)));
}

function openModal(article) {
  const content = document.getElementById("modal-content");
  content.innerHTML = `
    <div class="modal-header">
      <div class="modal-meta">
        <span class="company-badge">${article.company}</span>
        <span class="ticker-badge">${article.ticker}</span>
        <span class="card-category">${article.category}</span>
        <span class="sentiment-badge ${article.sentiment}">${SENTIMENT_LABEL[article.sentiment]}</span>
      </div>
      <div class="modal-title">${article.title}</div>
    </div>
    <div class="modal-body">${article.summary}</div>
    <div class="modal-tags">
      ${article.tags.map(t => `<span class="tag">${t}</span>`).join("")}
    </div>
    <div class="card-date" style="margin-top:20px">${article.date}</div>
  `;
  document.getElementById("modal-overlay").classList.add("open");
}

function closeModal() {
  document.getElementById("modal-overlay").classList.remove("open");
}

function initFilters() {
  document.querySelectorAll(".filter-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".filter-btn").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      activeFilter = btn.dataset.filter;
      renderGrid();
    });
  });

  document.getElementById("category-filter").addEventListener("change", e => {
    activeCategory = e.target.value;
    renderGrid();
  });

  document.getElementById("modal-close").addEventListener("click", closeModal);
  document.getElementById("modal-overlay").addEventListener("click", e => {
    if (e.target === document.getElementById("modal-overlay")) closeModal();
  });
  document.addEventListener("keydown", e => {
    if (e.key === "Escape") closeModal();
  });
}

async function init() {
  try {
    allArticles = await fetchNews();
    updateStats(allArticles);
    populateCategories(allArticles);
    renderGrid();
    initFilters();
  } catch (err) {
    document.getElementById("news-grid").innerHTML =
      '<div class="loading">載入失敗，請確認後端伺服器是否運行中。</div>';
    console.error(err);
  }
}

init();
