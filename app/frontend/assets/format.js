const labels = {
  merchant_name: "Merchant name", merchant_tax_id: "Merchant tax ID",
  merchant_address: "Merchant address", customer_id: "Customer ID",
  document_number: "Document number", issue_date: "Issue date", currency: "Currency",
  subtotal: "Subtotal", tax_amount: "Tax", discount: "Discount", total: "Total",
  payment_method: "Payment method", overall: "Overall confidence",
  status: "Status", attempts: "Processing attempts", last_error_code: "Last error code",
  updated_at: "Last updated", document_id: "Document ID", document_type: "Document type",
  description: "Description", quantity: "Quantity", unit_price: "Unit price", line_total: "Line total",
};
const monetary = new Set(["subtotal", "tax_amount", "discount", "total", "unit_price", "line_total"]);
export function label(name) {
  return labels[name] || name.replaceAll("_", " ").replace(/^./, first => first.toUpperCase());
}
export function date(value) {
  if (!value) return "Not found";
  const parsed = new Date(value);
  return Number.isFinite(parsed.getTime()) ? parsed.toLocaleString(undefined, {dateStyle: "medium", timeStyle: "short"}) : "Not found";
}
export function issueDate(value) {
  if (!value) return "Not found";
  const parsed = new Date(value + "T00:00:00Z");
  return Number.isFinite(parsed.getTime()) ? parsed.toLocaleDateString(undefined, {dateStyle: "medium", timeZone: "UTC"}) : "Not found";
}
export function money(result) {
  const data = result?.extracted_data;
  return data?.total !== null && data?.total !== undefined
    ? [data.currency, data.total].filter(value => value !== null && value !== undefined && value !== "").join(" ")
    : "Not found";
}
export function bytes(value) {
  if (!Number.isFinite(Number(value))) return "Size unavailable";
  return value < 1048576 ? (value / 1024).toFixed(1) + " KiB" : (value / 1048576).toFixed(2) + " MiB";
}
export function fileType(mime) {
  return {"application/pdf": "PDF", "image/png": "PNG", "image/jpeg": "JPEG"}[mime] || "Document";
}
export function confidence(value) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1
    ? Math.round(value * 100) + "%" : "Not available";
}
export function fieldValue(name, value, currency) {
  if (value === null || value === undefined) return "Not found";
  if (name === "issue_date") return issueDate(value);
  if (name === "updated_at") return date(value);
  if (monetary.has(name)) return [currency, String(value)].filter(Boolean).join(" ");
  if (name === "payment_method") return String(value).replaceAll("_", " ").replace(/^./, first => first.toUpperCase());
  return String(value);
}
export function listFields(target, values, currency = null) {
  const root = typeof target === "string" ? document.getElementById(target) : target;
  root.replaceChildren();
  for (const [name, value] of Object.entries(values)) {
    const group = document.createElement("div");
    const term = document.createElement("dt"), description = document.createElement("dd");
    term.textContent = label(name);
    description.textContent = fieldValue(name, value, currency);
    group.append(term, description);
    root.append(group);
  }
}
