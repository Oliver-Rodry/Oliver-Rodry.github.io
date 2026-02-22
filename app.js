async function loadProducts(target) {
const res = await fetch("products.csv");
const text = await res.text();

const rows = text.split("\n").slice(1);

const container = document.getElementById(target);

rows.forEach(row => {
if(!row) return;

const cols = row.split(",");
const name = cols[1];
const price = cols[3];

const div = document.createElement("div");
div.innerHTML = `<strong>${name}</strong><br>Precio: RD$ ${price}`;
container.appendChild(div);
});
}

if(document.getElementById("products")) {
loadProducts("products");
}
