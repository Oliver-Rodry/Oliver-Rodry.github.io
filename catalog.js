document.addEventListener("DOMContentLoaded", () => {
  const grid = document.getElementById("catalogGrid");
  const q = document.getElementById("q");
  const category = document.getElementById("category");
  const inStockOnly = document.getElementById("inStockOnly");
  const countPill = document.getElementById("countPill");

  const PAGE_SIZE = 10;

  let products = [];
  let filtered = [];
  let visibleCount = PAGE_SIZE;

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

  function statusHTML(stock) {
    const s = Number(stock || 0);
    if (s > 0) {
      return `<span class="status"><span class="dot dot--green"></span>Disponible · ${s} uds</span>`;
    }
    return `<span class="status"><span class="dot dot--orange"></span>En camino · ${s} uds</span>`;
  }

  function setLoading(isLoading) {
    if (!countPill) return;
    countPill.textContent = isLoading ? "Cargando..." : `${filtered.length} producto(s)`;
  }

  // Imagen: por defecto buscamos en /img/products/<SKU>.jpg
  function productImageUrl(p) {
    const sku = String(p.sku || "").trim();
    if (!sku) return "";
    // cache-bust suave (si cambias la foto, que se refresque)
    return `img/products/${encodeURIComponent(sku)}.jpg?v=1`;
  }

  function ensureLightbox() {
    if (document.getElementById("lightbox")) return;

    const el = document.createElement("div");
    el.id = "lightbox";
    el.className = "lightbox";
    el.innerHTML = `
      <div class="lightbox__backdrop" data-close="1"></div>
      <div class="lightbox__panel" role="dialog" aria-modal="true" aria-label="Vista del producto">
        <button class="lightbox__close" type="button" aria-label="Cerrar" data-close="1">×</button>
        <div class="lightbox__content">
          <div class="lightbox__imgWrap">
            <img class="lightbox__img" alt="" />
          </div>
          <div class="lightbox__info">
            <div class="lightbox__title" id="lbTitle"></div>
            <div class="lightbox__meta" id="lbMeta"></div>
            <div class="lightbox__desc" id="lbDesc"></div>
          </div>
        </div>
      </div>
    `;
    document.body.appendChild(el);

    el.addEventListener("click", (e) => {
      const t = e.target;
      if (t && t.dataset && t.dataset.close) closeLightbox();
    });

    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") closeLightbox();
    });
  }

  function openLightbox({ title, meta, desc, imgSrc }) {
    ensureLightbox();
    const lb = document.getElementById("lightbox");
    const img = lb.querySelector(".lightbox__img");
    const t = lb.querySelector("#lbTitle");
    const m = lb.querySelector("#lbMeta");
    const d = lb.querySelector("#lbDesc");

    t.textContent = title || "";
    m.textContent = meta || "";
    d.textContent = desc || "";

    img.src = imgSrc || "";
    img.alt = title || "Producto";

    // fallback si no existe imagen
    img.onerror = () => {
      img.removeAttribute("src");
      img.alt = "Sin imagen";
      img.closest(".lightbox__imgWrap").classList.add("is-empty");
    };
    img.onload = () => {
      img.closest(".lightbox__imgWrap").classList.remove("is-empty");
    };

    lb.classList.add("is-open");
    document.documentElement.classList.add("no-scroll");
  }

  function closeLightbox() {
    const lb = document.getElementById("lightbox");
    if (!lb) return;
    lb.classList.remove("is-open");
    document.documentElement.classList.remove("no-scroll");
  }

  // ---------- Rendering ----------
  function render() {
    if (!grid) return;

    const toShow = filtered.slice(0, visibleCount);
    const already = Math.min(visibleCount, filtered.length);

    if (!toShow.length) {
      grid.innerHTML = `
        <article class="product">
          <h3 class="product__name">Sin resultados</h3>
          <p class="product__desc">Prueba otra búsqueda o quita filtros.</p>
        </article>
      `;
      setLoading(false);
      return;
    }

    grid.innerHTML = toShow
      .map(p => {
        const skuLine = p.sku ? `<div class="product__sku">${escapeHTML(p.sku)}</div>` : "";
        const descLine = p.description
          ? `<p class="product__desc">${escapeHTML(p.description)}</p>`
          : "";

        const img = productImageUrl(p);
        const clickable = p.stock > 0 ? "product--clickable" : "";
        const clickHint = p.stock > 0 ? `<span class="product__hint">Toca para ver</span>` : "";

        // OJO: ponemos <img> siempre; si no existe, CSS muestra placeholder
        return `
          <article class="product ${clickable}" data-sku="${escapeHTML(p.sku || "")}" data-stock="${Number(p.stock || 0)}">
            <div class="product__media">
              <img class="product__img" src="${escapeHTML(img)}" alt="${escapeHTML(p.name || "Producto")}" loading="lazy" />
              <div class="product__imgFallback">Sin imagen</div>
            </div>

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
              <div class="product__right">
                ${statusHTML(p.stock)}
                ${clickHint}
              </div>
            </div>
          </article>
        `;
      })
      .join("");

    // click: solo si Disponible (stock>0)
    grid.querySelectorAll(".product.product--clickable").forEach(card => {
      card.addEventListener("click", () => {
        const sku = card.dataset.sku || "";
        const p = products.find(x => String(x.sku) === String(sku));
        if (!p || !(p.stock > 0)) return;

        openLightbox({
          title: `${p.name || "Producto"}`,
          meta: `${p.category || "General"} · ${formatDOP(p.price_dop)} · Disponible: ${Number(p.stock || 0)} uds`,
          desc: p.description || "",
          imgSrc: productImageUrl(p)
        });
      });
    });

    // Footer controls
    if (already < filtered.length) {
      grid.innerHTML += `
        <div style="grid-column:1/-1; display:flex; flex-direction:column; align-items:center; gap:10px; margin-top:8px;">
          <div class="pill pill--muted" style="text-align:center;">
            Mostrando ${already} de ${filtered.length}.
          </div>
          <button id="loadMoreBtn" class="btn btn--primary" type="button">
            Cargar 10 más
          </button>
        </div>
      `;
      const btn = document.getElementById("loadMoreBtn");
      if (btn) btn.addEventListener("click", loadMore);
    } else {
      grid.innerHTML += `
        <div class="pill pill--muted" style="text-align:center; grid-column:1/-1; margin-top:8px;">
          Fin del catálogo ✅
        </div>
      `;
    }

    setLoading(false);
  }

  function loadMore() {
    if (visibleCount < filtered.length) {
      visibleCount += PAGE_SIZE;
      render();
      // si pantalla grande y sigue sin scroll, deja el botón igual
      // (el usuario puede seguir tocando)
    }
  }

  function loadMoreIfNearBottom() {
    const nearBottom =
      window.innerHeight + window.scrollY >= document.body.offsetHeight - 600;
    if (!nearBottom) return;
    loadMore();
  }

  // ---------- Filtering ----------
  function applyFilters(reset = false) {
    const term = (q?.value || "").trim().toLowerCase();
    const cat = category?.value || "";
    const onlyStock = !!inStockOnly?.checked;

    filtered = products.filter(p => {
      if (cat && p.category !== cat) return false;
      if (onlyStock && !(p.stock > 0)) return false;

      if (term) {
        const hay = `${p.sku} ${p.name} ${p.category} ${p.description}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });

    // Disponible primero
    filtered.sort((a, b) => {
      const as = a.stock > 0 ? 0 : 1;
      const bs = b.stock > 0 ? 0 : 1;
      if (as !== bs) return as - bs;
      const c = a.category.localeCompare(b.category, "es");
      if (c !== 0) return c;
      return a.name.localeCompare(b.name, "es");
    });

    if (reset) visibleCount = PAGE_SIZE;
    render();
    setLoading(false);
  }

  // ---------- Load data ----------
  async function load() {
    setLoading(true);

    // cache bust + no-store para reducir cache raro en GH Pages
    const res = await fetch(`products.csv?v=${Date.now()}`, { cache: "no-store" });
    if (!res.ok) throw new Error(`No se pudo cargar products.csv (HTTP ${res.status})`);

    const text = await res.text();
    const raw = parseCSV(text);
    if (!raw.length) throw new Error("products.csv está vacío o tiene formato inválido.");

    products = raw.map(p => ({
      sku: p.sku || "",
      name: p.name || "",
      category: p.category || "General",
      price_dop: Number(p.price_dop || 0),
      stock: Number(p.stock || 0),
      description: p.description || ""
    }));

    // Categories dropdown
    const cats = [...new Set(products.map(p => p.category).filter(Boolean))]
      .sort((a, b) => a.localeCompare(b, "es"));

    if (category) {
      category.innerHTML = `<option value="">Todas</option>`;
      cats.forEach(c => {
        const opt = document.createElement("option");
        opt.value = c;
        opt.textContent = c;
        category.appendChild(opt);
      });
    }

    applyFilters(true);
  }

  // ---------- Events ----------
  q?.addEventListener("input", () => applyFilters(true));
  category?.addEventListener("change", () => applyFilters(true));
  inStockOnly?.addEventListener("change", () => applyFilters(true));
  window.addEventListener("scroll", loadMoreIfNearBottom, { passive: true });

  // ---------- Start ----------
  load().catch(err => {
    setLoading(false);
    if (countPill) countPill.textContent = "0 producto(s)";
    if (grid) {
      grid.innerHTML = `
        <article class="product">
          <h3 class="product__name">No se pudo cargar el catálogo</h3>
          <p class="product__desc">${escapeHTML(err.message)}</p>
          <p class="product__desc">
            Prueba abrir: <a class="btn" href="products.csv" target="_blank" rel="noopener">products.csv</a>
          </p>
        </article>
      `;
    }
  });
});
