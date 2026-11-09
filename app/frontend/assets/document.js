import {api, guard, notice, attachLogout} from "./api.js";
import {listFields} from "./format.js";
const id = new URLSearchParams(location.search).get("id");
const deadline = Date.now() + 300000;
let active = true, timer = null;
window.addEventListener("docuprocess:leave", () => { active = false; clearTimeout(timer); }, {once:true});
async function load() {
  try {
    const item = await api("/documents/" + encodeURIComponent(id));
    if (!active) return;
    document.getElementById("filename").textContent = item.filename;
    listFields("processing", item.processing);
    const result = item.result;
    listFields("fields", result ? Object.fromEntries(Object.entries(result.extracted_data).filter(([key]) => key !== "line_items")) : {}, result?.extracted_data.currency);
    listFields("confidence", result ? {overall:result.confidence.overall, ...result.confidence.fields} : {});
    const lineItems = document.getElementById("line-items"); lineItems.replaceChildren();
    const entries = result?.extracted_data.line_items || [];
    if (!entries.length) lineItems.textContent = result ? "No line items detected." : "Pending";
    for (const entry of entries) {
      const row = document.createElement("dl");
      listLineItem(row, entry, result.extracted_data.currency);
      lineItems.append(row);
    }
    const warnings = document.getElementById("warnings"); warnings.replaceChildren();
    for (const warning of result?.validation.warnings || []) {
      const li = document.createElement("li"); li.textContent = warning.code + (warning.field ? " (" + warning.field + ")" : "") + ": " + warning.message; warnings.append(li);
    }
    if (result?.error) notice(result.error.message);
    if (["PENDING","RUNNING"].includes(item.processing.status)) {
      if (Date.now() < deadline) timer = setTimeout(load, 5000); else notice("Still processing. Refresh later.");
    }
  } catch (error) { if (active) notice(error.message); }
}
if (guard()) { attachLogout(); if (id) load(); else notice("Choose a document from the dashboard."); }

function listLineItem(root, entry, currency) {
  for (const [name, value] of Object.entries(entry)) {
    const label = document.createElement("dt"), item = document.createElement("dd");
    label.textContent = name.replaceAll("_", " ");
    item.textContent = value === null ? "Not found" : ((currency && ["unit_price", "line_total"].includes(name) ? currency + " " : "") + String(value));
    root.append(label, item);
  }
}
