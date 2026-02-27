// index.js (FULL REPLACEMENT)

document.addEventListener("DOMContentLoaded", async () => {
  const grid = document.getElementById("featuredProducts");
  if (!grid) return;

  // ---------- Helpers ----------
  function escapeHTML(s) {
    return String(s ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

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

  // Robust CSV parser (supports quotes + commas inside fields)
  function parseCSV(text) {
    const rows = [];
    let row = [];
    let field = "";
    let inQuotes = false;

    for (let i = 0; i < text.length; i++) {
      const c = text[i];
      const next = text[i + 1];

      if (c === '"' && inQuotes && next === '"') {
        field += '"';
        i++;
        continue;
      }
      if (c === '"') {
        inQuotes = !inQuotes;
        continue;
      }
      if (c === "," && !inQuotes) {
        row.push(field);
        field = "";
        continue;
      }
      if ((c === "\n" || c === "\r") && !inQuotes) {
        if (c === "\r" && next === "\n") i++;
        row.push(field);
        field = "";
        if (row.some(v => v.trim() !== "")) rows.push(row);
        row = [];
        continue;
      }
      field += c;
    }

    row.push(field);
    if (row.some(v => v.trim() !== "")) rows.push(row);

    if (rows.length < 2) return [];
    const headers = rows[0].map(h => h.trim());
    const out = [];

    for (let r = 1; r < rows.length; r++) {
      const obj = {};
      for (let c = 0; c < headers.length; c++) {
        obj[headers[c]] = (rows[r][c] ?? "").trim();
      }
      out.push(obj);
    }
    return out;
  }

  // Image naming rule (same as catalog.js)
  function productImageUrl(p) {
    const sku = String(p?.sku || "").trim();
    if (!sku) return "";
    return `img/products/${encodeURIComponent(sku)}.jpg?v=1`;
  }

  function imgMediaHTML(p) {
    const url = productImageUrl(p);
    if (!url) return "";

    return `
      <div class="product__media">
        <img class="product__img"
             src="${escapeHTML(url)}"
             alt="${escapeHTML(p.name || "Producto")}"
             loading="lazy"
             onerror="this.closest('.product__media')?.remove()" />
      </div>
    `;
  }

  // ---------- Lightbox (same behavior as catalog) ----------
  function ensureLightbox() {
    if (document.getElementById("lightbox")) return;

    document.body.insertAdjacentHTML(
      "beforeend",
      `
      <div id="lightbox" class="lightbox" aria-hidden="true">
        <div class="lightbox__backdrop" data-close="1"></div>
        <div class="lightbox__panel" role="dialog" aria-modal="true">
          <button class="lightbox__close" type="button" aria-label="Cerrar" data-close="1">✕</button>

          <div class="lightbox__imgWrap">
            <img class="lightbox__img" alt="" />
          </div>

          <div class="lightbox__body">
            <div id="lbTitle" class="lightbox__title"></div>
            <div id="lbMeta" class="lightbox__meta"></div>
            <div id="lbDesc" class="lightbox__desc"></div>
          </div>
        </div>
      </div>
      `
    );

    const lb = document.getElementById("lightbox");

    lb.addEventListener("click", (e) => {
      if (e.target?.dataset?.close) closeLightbox();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeLightbox();
    });
  }

  function closeLightbox() {
    const lb = document.getElementById("lightbox");
    if (!lb) return;
    lb.classList.remove("is-open");
    document.documentElement.classList.remove("no-scroll");
  }

  function openLightbox({ title, meta, desc, imgSrc }) {
    ensureLightbox();

    const lb = document.getElementById("lightbox");
    const img = lb.querySelector(".lightbox__img");
    const t = lb.querySelector("#lbTitle");
    const m = lb.querySelector("#lbMeta");
    const d = lb.querySelector("#lbDesc");
    const wrap = img.closest(".lightbox__imgWrap");

    t.textContent = title || "";
    m.textContent = meta || "";

    const cleanDesc = (desc || "").trim();
    if (cleanDesc) {
      d.style.display = "block";
      d.textContent = cleanDesc;
    } else {
      d.style.display = "none";
      d.textContent = "";
    }

    wrap.classList.remove("is-empty");

    img.src = imgSrc || "";
    img.alt = title || "Producto";

    img.onerror = () => {
      img.removeAttribute("src");
      img.alt = "Sin imagen";
      wrap.classList.add("is-empty");
    };

    lb.classList.add("is-open");
    document.documentElement.classList.add("no-scroll");
  }

  // ---------- Load & Render ----------
  let products = [];

  function renderFeatured(items) {
    // show only product cards in the grid (no extra “Catálogo” card inside the 6)
    grid.innerHTML = items
      .map((p) => {
        const skuLine = p.sku ? `<div class="product__sku">${escapeHTML(p.sku)}</div>` : "";
        const descLine = p.description ? `<p class="product__desc">${escapeHTML(p.description)}</p>` : "";

        // clickable always (even if no stock) — if you want ONLY in-stock clickable, change to: Number(p.stock||0)>0
        return `
          <article class="product product--clickable" data-sku="${escapeHTML(p.sku || "")}">
            ${imgMediaHTML(p)}

            <div class="product__top">
              <div>
                <h3 class="product__name">${escapeHTML(p.name || "Producto")}</h3>
                ${skuLine}
              </div>
              <div class="price">${formatDOP(p.price_dop)}</div>
            </div>

            ${descLine}

            <div class="product__row">
              <span class="tag">${escapeHTML(p.category || "General")}</span>
              ${statusHTML(p.stock)}
            </div>
          </article>
        `;
      })
      .join("");

    // one click handler (delegation)
    grid.onclick = (e) => {
      const card = e.target.closest(".product--clickable");
      if (!card) return;

      const sku = card.dataset.sku || "";
      const p = products.find((x) => String(x.sku) === String(sku));
      if (!p) return;

      openLightbox({
        title: p.name || "Producto",
        meta: `${p.category || "General"} · ${formatDOP(p.price_dop)} · ${Number(p.stock || 0) > 0 ? `Disponible: ${Number(p.stock || 0)} uds` : "En camino"}`,
        desc: p.description || "",
        imgSrc: productImageUrl(p)
      });
    };
  }

  try {
    const res = await fetch(`products.csv?v=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error("No se pudo cargar products.csv");

    const text = await res.text();
    const raw = parseCSV(text);

    products = raw.map((p) => ({
      sku: p.sku || "",
      name: p.name || "",
      category: p.category || "General",
      price_dop: Number(p.price_dop || 0),
      stock: Number(p.stock || 0),
      description: p.description || ""
    }));

    // pick 6: in-stock first
    const featured = [...products]
      .sort((a, b) => (Number(b.stock || 0) > 0) - (Number(a.stock || 0) > 0))
      .slice(0, 6);

    renderFeatured(featured);

  } catch (e) {
    grid.innerHTML = `
      <article class="card">
        <h3>Destacados</h3>
        <p class="small">No se pudieron cargar los productos. Abre el catálogo:</p>
        <a class="btn btn--primary" href="catalog.html?v=5">Abrir catálogo completo</a>
      </article>
    `;
  }
});
