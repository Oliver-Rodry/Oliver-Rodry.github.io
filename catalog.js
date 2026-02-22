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

  function parseCSV(text) {
    const lines = text.trim().split(/\r?\n/);
    const headers = lines[0].split(",");
    return lines.slice(1).map(line => {
      const values = line.split(",");
      const obj = {};
      headers.forEach((h, i) => obj[h.trim()] = (values[i] || "").trim());
      return obj;
    });
  }

  function escapeHTML(str) {
    return String(str || "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;");
  }

  let products = [];

  async function load() {
    const res = await fetch("products.csv?v=" + Date.now());
    if (!res.ok) {
      grid.innerHTML = "<p>No se pudo cargar el catálogo.</p>";
      return;
    }

    const text = await res.text();
    products = parseCSV(text);

    const categories = [...new Set(products.map(p => p.category))];
    category.innerHTML = '<option value="">Todas</option>';
    categories.forEach(cat => {
      const opt = document.createElement("option");
      opt.value = cat;
      opt.textContent = cat;
      category.appendChild(opt);
    });

    render();
  }

  function render() {
    const search = q.value.toLowerCase();
    const selectedCategory = category.value;
    const onlyStock = inStockOnly.checked;

    const filtered = products.filter(p => {
      if (selectedCategory && p.category !== selectedCategory) return false;
      if (onlyStock && Number(p.stock) <= 0) return false;

      const text = (p.name + p.category + p.description).toLowerCase();
      return text.includes(search);
    });

    countPill.textContent = filtered.length + " producto(s)";

    grid.innerHTML = filtered.map(p => `
      <div class="product">
        <h3>${escapeHTML(p.name)}</h3>
        <p>${escapeHTML(p.description)}</p>
        <strong>${formatDOP(p.price_dop)}</strong>
      </div>
    `).join("");
  }

  q.addEventListener("input", render);
  category.addEventListener("change", render);
  inStockOnly.addEventListener("change", render);

  load();
});
