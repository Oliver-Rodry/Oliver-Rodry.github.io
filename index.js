document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("featuredProducts");
  if (!grid) return;

  function formatDOP(value) {
    return new Intl.NumberFormat("es-DO", {
      style: "currency",
      currency: "DOP",
      maximumFractionDigits: 0
    }).format(Number(value || 0));
  }
function statusHTML(stock) {
  const s = Number(stock || 0);
  if (s > 0) {
    return `<span class="status"><span class="dot dot--green"></span>Disponible · ${s} uds</span>`;
  }
  return `<span class="status"><span class="dot dot--orange"></span>En camino · ${s} uds</span>`;
}
  function escapeHTML(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

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

  try {
    const res = await fetch(`products.csv?v=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("No se pudo cargar products.csv");

    const text = await res.text();
    const raw = parseCSV(text);

    const products = raw.map(p => ({
      sku: p.sku || "",
      name: p.name || "",
      category: p.category || "General",
      price_dop: Number(p.price_dop || 0),
      stock: Number(p.stock || 0),
      description: p.description || ""
    }));

    // Pick first 6 items; show in-stock first
    const featured = products
      .sort((a,b) => (b.stock > 0) - (a.stock > 0))
      .slice(0, 6);

    grid.innerHTML = featured.map(p => {
      const stockText = p.stock > 0 ? `En stock: ${p.stock}` : "Agotado / Bajo pedido";
      const stockClass = p.stock > 0 ? "tag--ok" : "tag--no";

      return `
        <article class="product">
          <div class="product__top">
            <div>
              <h3 class="product__name">${escapeHTML(p.name)}</h3>
              ${p.sku ? `<div class="product__sku">${escapeHTML(p.sku)}</div>` : ""}
            </div>
            <div class="price">${formatDOP(p.price_dop)}</div>
          </div>

          ${p.description ? `<p class="product__desc">${escapeHTML(p.description)}</p>` : ""}

          <div class="product__row">
            <span class="tag">${escapeHTML(p.category)}</span>
            <span class="tag ${stockClass}">${escapeHTML(stockText)}</span>
          </div>
        </article>
      `;
    }).join("");

    // Add a final “View full catalog” button card if you want (optional)
    // grid.innerHTML += `
    //   <article class="product">
    //     <h3 class="product__name">Ver todo</h3>
    //     <p class="product__desc">Entra al catálogo completo para ver todos los productos y precios.</p>
    //     <a class="btn btn--primary" href="catalog.html?v=1">Abrir catálogo completo</a>
    //   </article>
    // `;
  } catch (e) {
    grid.innerHTML = `
      <article class="card">
        <h3>Destacados</h3>
        <p class="small">No se pudieron cargar los productos. Abre el catálogo:</p>
        <a class="btn btn--primary" href="catalog.html?v=1">Abrir catálogo completo</a>
      </article>
    `;
  }
});
