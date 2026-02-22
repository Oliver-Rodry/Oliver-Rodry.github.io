const WHATSAPP_NUMBER = "18493547326";
const WHATSAPP_DEFAULT_TEXT = "Hola! Quiero una cotización / información sobre:";

function formatDOP(value) {
  const n = Number(value || 0);
  return new Intl.NumberFormat("es-DO", {
    style: "currency",
    currency: "DOP",
    maximumFractionDigits: 0
  }).format(n);
}

function setWhatsAppLinks() {
  const href = `https://wa.me/${WHATSAPP_NUMBER}?text=${encodeURIComponent(WHATSAPP_DEFAULT_TEXT)}`;
  ["btnWhatsapp", "btnWhatsapp2", "btnWhatsapp3"].forEach(id => {
    const el = document.getElementById(id);
    if (el) el.href = href;
  });
}

function escapeHTML(s) {
  return String(s ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function splitCSVLine(line) {
  const out = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') { cur += '"'; i++; }
      else inQuotes = !inQuotes;
    } else if (ch === "," && !inQuotes) {
      out.push(cur); cur = "";
    } else cur += ch;
  }
  out.push(cur);
  return out;
}

function parseCSV(csvText) {
  const lines = csvText.trim().split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];
  const headers = splitCSVLine(lines[0]).map(h => h.trim());
  return lines.slice(1).map(line => {
    const cols = splitCSVLine(line);
    const obj = {};
    headers.forEach((h, i) => obj[h] = (cols[i] ?? "").trim());
    return obj;
  });
}

async function tryRenderFeatured() {
  const el = document.getElementById("featuredProducts");
  if (!el) return;

  try {
    const res = await fetch("products.csv", { cache: "no-store" });
    if (!res.ok) throw new Error("No products.csv");
    const text = await res.text();
    const items = parseCSV(text).slice(0, 6);

    el.innerHTML = items.map(p => `
      <article class="card">
        <h3>${escapeHTML(p.name || "Producto")}</h3>
        <p class="small">${escapeHTML(p.category || "Categoría")}</p>
        <p class="price">${formatDOP(p.price_dop)}</p>
        <p class="small">${Number(p.stock) > 0 ? "Disponible" : "Agotado / Bajo pedido"}</p>
      </article>
    `).join("");
  } catch {
    el.innerHTML = `
      <article class="card">
        <h3>Catálogo listo</h3>
        <p class="small">Agrega productos en <code>products.csv</code> para mostrar destacados aquí.</p>
      </article>
    `;
  }
}

document.addEventListener("DOMContentLoaded", () => {
  setWhatsAppLinks();
  const y = document.getElementById("year");
  if (y) y.textContent = String(new Date().getFullYear());
  tryRenderFeatured();
});

window.__PSN__ = { formatDOP, parseCSV, escapeHTML };
