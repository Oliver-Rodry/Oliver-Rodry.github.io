document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("catalogGrid");
  const q = document.getElementById("q");
  const category = document.getElementById("category");
  const inStockOnly = document.getElementById("inStockOnly");
  const countPill = document.getElementById("countPill");

  // --- Helpers ---
  function formatDOP(value) {
    return new Intl.NumberFormat("es-DO", {
      style: "currency",
      currency: "DOP",
      maximumFractionDigits: 0
    }).format(Number(value || 0));
  }

  function escapeHTML(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  // Simple CSV parser (works with your current export; avoid commas inside fields)
  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/).filter(Boolean);
    if (lines.length < 2) return [];
    const headers = lines[0].split(",").map(h => h.trim());

    return lines.slice(1).map(line => {
      const cols = line.split(",");
      const obj = {};
      headers.forEach((h, i) => obj[h] = (cols[i] ?? "").trim());
      return obj;
    });
  }

  // --- State ---
  const PAGE_SIZE = 10;
  let products = [];
  let filtered = [];
  let visibleCount = PAGE_SIZE;

  function buildStatus(stock) {
    return stock > 0
      ? `<span class="status"><span class="dot dot--green"></span>Disponible</span>`
      : `<span class="status"><span class="dot dot--orange"></span>En camino</span>`;
  }

  async function load() {
    const res = await fetch(`products.csv?v=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`No se pudo cargar products.csv (HTTP ${res.status})`);

    const text = await res.text();
    const raw = parseCSV(text);
    if (!raw.length) throw new Error("products.csv está vacío.");

    products = raw.map(p => ({
      sku: p.sku || "",
      name: p.name || "",
      category: p.category || "General",
      price_dop: Number(p.price_dop || 0),
      stock: Number(p.stock || 0),
      description: p.description || ""
    }));

    // Fill categories dropdown
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))]
      .sort((a,b)=>a.localeCompare(b,"es"));

    category.innerHTML = `<option value="">Todas</option>`;
    cats.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      category.appendChild(opt);
    });

    applyFilters(true);
  }

  function applyFilters(reset = false) {
    const term = (q.value || "").trim().toLowerCase();
    const cat = category.value;
    const onlyStock = inStockOnly.checked;

    filtered = products.filter(p => {
      if (cat && p.category !== cat) return false;
      if (onlyStock && !(p.stock > 0)) return false;
      if (term) {
        const hay = `${p.sku} ${p.name} ${p.category} ${p.description}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });

    // Sort: disponible first, then category, then name
    filtered.sort((a,b) => {
      const as = a.stock > 0 ? 0 : 1;
      const bs = b.stock > 0 ? 0 : 1;
      if (as !== bs) return as - bs;
      const c = a.category.localeCompare(b.category, "es");
      if (c !== 0) return c;
      return a.name.localeCompare(b.name, "es");
    });

    if (reset) visibleCount = PAGE_SIZE;
    render(true);
  }

  function render(clear = false) {
    countPill.textContent = `${filtered.length} producto(s)`;

    if (clear) grid.innerHTML = "";

    const toShow = filtered.slice(0, visibleCount);

    // If empty
    if (!toShow.length) {
      grid.innerHTML = `
        <article class="product">
          <h3 class="product__name">Sin resultados</h3>
          <p class="product__desc">Prueba otra búsqueda o quita filtros.</p>
        </article>
      `;
      return;
    }

    grid.innerHTML = toShow.map(p => {
      const skuLine = p.sku ? `<div class="product__sku">${escapeHTML(p.sku)}</div>` : "";
      const descLine = p.description ? `<p class="product__desc">${escapeHTML(p.description)}</p>` : "";

      return `
        <article class="product">
          <div class="product__top">
            <div>
              <h3 class="product__name">${escapeHTML(p.name || "Producto")}</h3>
              ${skuLine}
            </div>
            <div class="price">${formatDOP(p.price_dop)}</div>
          </div>

          ${descLine}

          <div class="product__row">
            <span class="tag">${escapeHTML(p.category)}</span>
            ${buildStatus(p.stock)}
          </div>
        </article>
      `;
    }).join("");

    // Add a small “loading more” indicator at the end (optional)
    const already = Math.min(visibleCount, filtered.length);
    if (already < filtered.length) {
      grid.innerHTML += `
        <div class="pill pill--muted" style="text-align:center; grid-column: 1/-1;">
          Mostrando ${already} de ${filtered.length}. Desliza para cargar más…
        </div>
      `;
    }
  }

  function loadMoreIfNeeded() {
    // When user is near bottom, add 10 more
    const nearBottom = window.innerHeight + window.scrollY >= document.body.offsetHeight - 600;
    if (!nearBottom) return;

    if (visibleCount < filtered.length) {
      visibleCount += PAGE_SIZE;
      render(true);
    }
  }

  // Event listeners
  q.addEventListener("input", () => applyFilters(true));
  category.addEventListener("change", () => applyFilters(true));
  inStockOnly.addEventListener("change", () => applyFilters(true));
  window.addEventListener("scroll", loadMoreIfNeeded, { passive: true });

  try {
    await load();
  } catch (e) {
    countPill.textContent = "0 producto(s)";
    grid.innerHTML = `
      <article class="product">
        <h3 class="product__name">No se pudo cargar el catálogo</h3>
        <p class="product__desc">${escapeHTML(e.message)}</p>
        <p class="product__desc">
          Prueba abrir: <a class="btn" href="products.csv" target="_blank" rel="noopener">products.csv</a>
        </p>
      </article>
    `;
  }
});
