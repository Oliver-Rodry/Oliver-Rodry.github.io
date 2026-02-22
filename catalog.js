document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("catalogGrid");
  const q = document.getElementById("q");
  const category = document.getElementById("category");
  const inStockOnly = document.getElementById("inStockOnly");
  const countPill = document.getElementById("countPill");

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

  // Simple CSV parser (works for your current file)
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

  let products = [];

  async function load() {
    // cache bust so updates show instantly
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

    // Fill category dropdown
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))]
      .sort((a,b)=>a.localeCompare(b,"es"));

    category.innerHTML = `<option value="">Todas</option>`;
    cats.forEach(c => {
      const opt = document.createElement("option");
      opt.value = c;
      opt.textContent = c;
      category.appendChild(opt);
    });

    render();
  }

  function render() {
    const term = (q.value || "").trim().toLowerCase();
    const cat = category.value;
    const onlyStock = inStockOnly.checked;

    let filtered = products.filter(p => {
      if (cat && p.category !== cat) return false;
      if (onlyStock && !(p.stock > 0)) return false;
      if (term) {
        const hay = `${p.sku} ${p.name} ${p.category} ${p.description}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });

    // Sort: in-stock first, then category, then name
    filtered.sort((a,b) => {
      const as = a.stock > 0 ? 0 : 1;
      const bs = b.stock > 0 ? 0 : 1;
      if (as !== bs) return as - bs;
      const c = a.category.localeCompare(b.category, "es");
      if (c !== 0) return c;
      return a.name.localeCompare(b.name, "es");
    });

    countPill.textContent = `${filtered.length} producto(s)`;

    grid.innerHTML = filtered.map(p => {
      const stockTag = p.stock > 0
        ? `<span class="tag tag--ok">En stock: ${p.stock}</span>`
        : `<span class="tag tag--no">Agotado / Bajo pedido</span>`;

      const skuLine = p.sku ? `<div class="product__sku">${escapeHTML(p.sku)}</div>` : "";

      return `
        <article class="product">
          <div class="product__top">
            <div>
              <h3 class="product__name">${escapeHTML(p.name || "Producto")}</h3>
              ${skuLine}
            </div>
            <div class="price">${formatDOP(p.price_dop)}</div>
          </div>

          ${p.description ? `<p class="product__desc">${escapeHTML(p.description)}</p>` : ""}

          <div class="product__row">
            <span class="tag">${escapeHTML(p.category)}</span>
            ${stockTag}
          </div>
        </article>
      `;
    }).join("");

    if (!filtered.length) {
      grid.innerHTML = `
        <article class="product">
          <h3 class="product__name">Sin resultados</h3>
          <p class="product__desc">Prueba otra búsqueda o quita filtros.</p>
        </article>
      `;
    }
  }

  q.addEventListener("input", render);
  category.addEventListener("change", render);
  inStockOnly.addEventListener("change", render);

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
