export function date(value) { return value ? new Date(value).toLocaleString() : "Not found"; }
export function money(result) {
  const data = result?.extracted_data;
  return data?.total !== null && data?.total !== undefined ? (data.currency || "") + " " + data.total : "Not found";
}
export function listFields(target, values, currency = null) {
  const root = document.getElementById(target);
  root.replaceChildren();
  for (const [name, value] of Object.entries(values)) {
    const label = document.createElement("dt"), item = document.createElement("dd");
    label.textContent = name.replaceAll("_"," ");
    item.textContent = value === null || value === undefined ? "Not found" : ((currency && ["subtotal", "tax_amount", "discount", "total"].includes(name) ? currency + " " : "") + String(value));
    root.append(label, item);
  }
}
