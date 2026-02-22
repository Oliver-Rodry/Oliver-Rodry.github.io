document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("catalogGrid");
  const q = document.getElementById("q");
  const category = document.getElementById("category");
  const inStockOnly = document.getElementById("inStockOnly");
  const countPill = document.getElementById("countPill");

  const { formatDOP, parseCSV, escapeHTML } = window.__PSN__;

  let products = [];

  async function load() {
    const res = await fetch("products.csv", { cache: "no-store" });
    if (!res.ok) throw new Error("products.csv not found");
    const text = await res.text();

    products = parseCSV(text).map(p => ({
      sku: p.sku || "",
      name: p.name || "",
      category: p.category || "General",
      price_dop: Number(p.price_dop || 0),
      stock: Number(p.stock || 0),
      description: p.description || ""
    }));

    // fill categories
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))]
      .sort((a,b)=>a.localeCompare(b,"es"));
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

    const filtered = products.filter(p => {
      if (cat && p.category !== cat) return false;
      if (onlyStock && !(p.stock > 0)) return false;

      if (term) {
        const hay = `${p.sku} ${p.name} ${p.category} ${p.description}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });

    countPill.textContent = `${filtered.length} producto(s)`;

    grid.innerHTML = filtered.map(p => {
      const stockTag = p.stock > 0
        ? `<span class="tag tag--ok">En stock: ${p.stock}</span>`
        : `<span class="tag tag--no">Agotado / Bajo pedido</span>`;

      return `
        <article class="product">
          <div class="product__top">
            <div>
              <h3 class="product__name">${escapeHTML(p.name || "Producto")}</h3>
              <div class="product__sku">${escapeHTML(p.sku)}</div>
            </div>
            <div class="price">${formatDOP(p.price_dop)}</div>
          </div>

          <p class="product__desc">${escapeHTML(p.description)}</p>

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
        <h3 class="product__name">No se encontró el inventario</h3>
        <p class="product__desc">Verifica que <code>products.csv</code> exista en la raíz del repositorio.</p>
      </article>
    `;
  }
});
