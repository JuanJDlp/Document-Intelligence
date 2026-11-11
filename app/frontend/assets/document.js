import {api, guard, notice} from "./api.js";
import {bytes, confidence, date, fieldValue, fileType, issueDate, label, listFields, money} from "./format.js";
import {attachWorkspace, badge, buttonBusy, confidenceFields} from "./ui.js";

const id = new URLSearchParams(location.search).get("id");
const controller = new AbortController();
let deadline = Date.now() + 300000, active = true, timer = null, loading = false, lastItem = null;
const refresh = document.getElementById("refresh-document");
window.addEventListener("docuprocess:leave", () => {
  active = false; clearTimeout(timer); controller.abort();
}, {once: true});

const errors = {
  DOCUMENT_NOT_FOUND: "The uploaded document could not be found.",
  INVALID_DOCUMENT: "The document could not be processed. Try a valid one-page PDF, PNG or JPEG.",
  WORKER_TIMEOUT: "Processing took too long. Please try uploading the document again.",
  WORKER_RESULT_TOO_LARGE: "The extracted result was too large to save. Try a simpler document.",
  WORKER_LEASE_EXPIRED: "Processing could not finish after several attempts. Please upload the document again.",
};
function progress(item) {
  const state = item.processing.status;
  const terminal = ["COMPLETED", "PARTIAL", "FAILED"].includes(state);
  const stage = terminal ? 2 : state === "RUNNING" ? 1 : 0;
  for (const [index, name] of ["received", "processing", "result"].entries()) {
    const node = document.getElementById("step-" + name);
    node.className = index < stage ? "is-complete" : index === stage ? (state === "FAILED" ? "is-failed" : "is-current") : "";
    if (index === stage) node.setAttribute("aria-current", "step"); else node.removeAttribute("aria-current");
  }
  const messages = {
    PENDING: "Your document has been received and is waiting to be processed.",
    RUNNING: "We’re reading your document. This page will update automatically.",
    COMPLETED: "Processing is complete. Review the extracted details below.",
    PARTIAL: "Some details could not be found. Review the available information and notes below.",
    FAILED: "Processing could not be completed. Check the message below before trying again.",
  };
  document.getElementById("processing-message").textContent = messages[state] || "Checking processing status.";
}
function lineItems(result) {
  const root = document.getElementById("line-items");
  root.replaceChildren();
  const entries = result?.extracted_data.line_items || [];
  root.className = entries.length ? "table-wrap" : "line-items-empty";
  if (!entries.length) {
    root.textContent = result ? "No line items detected in this document." : "Line items will appear after extraction.";
    return;
  }
  const table = document.createElement("table"), head = document.createElement("thead"), row = document.createElement("tr"), body = document.createElement("tbody");
  const keys = ["description", "quantity", "unit_price", "line_total"];
  for (const key of keys) {
    const cell = document.createElement("th"); cell.scope = "col"; cell.textContent = label(key); row.append(cell);
  }
  head.append(row); table.append(head, body);
  for (const item of entries) {
    const row = document.createElement("tr");
    for (const key of keys) {
      const cell = document.createElement("td");
      cell.textContent = fieldValue(key, item[key], result.extracted_data.currency); row.append(cell);
    }
    body.append(row);
  }
  root.append(table);
}
function warnings(result) {
  const list = document.getElementById("warnings");
  list.replaceChildren();
  const entries = result?.validation.warnings || [];
  document.getElementById("warning-count").textContent = result ? entries.length : "—";
  const empty = document.getElementById("warnings-empty");
  empty.hidden = entries.length > 0;
  empty.textContent = result ? "No validation warnings." : "Validation notes will appear after processing.";
  for (const entry of entries) {
    const item = document.createElement("li"), title = document.createElement("strong"), message = document.createElement("span");
    title.textContent = label(entry.code.toLowerCase()) + (entry.field !== null && entry.field !== undefined ? " · " + label(entry.field) : "");
    message.textContent = entry.message;
    item.append(title, message); list.append(item);
  }
}
function render(item) {
  lastItem = item;
  const result = item.result, data = result?.extracted_data, state = item.processing.status;
  document.title = item.filename + " | DocuProcess Cloud";
  document.getElementById("filename").textContent = item.filename;
  document.getElementById("document-meta").textContent = fileType(item.mime_type) + " · " + bytes(item.size_bytes) + " · Uploaded " + date(item.created_at);
  document.getElementById("document-status").replaceChildren(badge(state));
  progress(item);
  document.getElementById("summary-total").textContent = result ? money(result) : "—";
  document.getElementById("summary-total-note").textContent = result ? "Amount read from your document" : "Available after extraction";
  document.getElementById("summary-merchant").textContent = result ? data.merchant_name ?? "Not found" : "—";
  document.getElementById("summary-date").textContent = result ? issueDate(data.issue_date) : "—";
  document.getElementById("summary-confidence").textContent = result ? confidence(result.confidence.overall) : "—";
  if (result) {
    listFields("fields", Object.fromEntries(Object.entries(data).filter(([key]) => key !== "line_items")), data.currency);
    confidenceFields(document.getElementById("confidence"), {overall: result.confidence.overall, ...result.confidence.fields});
  } else {
    document.getElementById("fields").replaceChildren();
    const placeholder = document.createElement("div");
    placeholder.className = "field-placeholder";
    placeholder.textContent = state === "FAILED" ? "No extraction result is available for this document." : "The extracted details will appear after processing.";
    document.getElementById("fields").append(placeholder);
    const empty = document.createElement("p"); empty.className = "field-help"; empty.textContent = "Confidence scores will appear after extraction.";
    document.getElementById("confidence").replaceChildren(empty);
  }
  listFields("processing", {...item.processing, document_id: item.document_id});
  lineItems(result); warnings(result); notice("");
  if (state === "FAILED") {
    notice(result?.error?.message || errors[item.processing.last_error_code] || "We couldn’t process this document. Try uploading a clearer copy.");
  }
  if (["PENDING", "RUNNING"].includes(state)) {
    if (Date.now() < deadline) timer = setTimeout(() => load(), 5000);
    else document.getElementById("processing-message").textContent = "Still processing. Refresh later to check for the result.";
  }
}
async function load(manual = false) {
  if (!active || loading) return;
  loading = true; clearTimeout(timer);
  if (manual) deadline = Date.now() + 300000;
  buttonBusy(refresh, true, "Refreshing…");
  try {
    const item = await api("/documents/" + encodeURIComponent(id), {signal: controller.signal});
    if (active) render(item);
  } catch (error) {
    if (!active || error.name === "AbortError") return;
    notice(error.message);
    if (!lastItem) {
      document.getElementById("document-meta").textContent = "Document information couldn’t be loaded.";
      document.getElementById("processing-message").textContent = "Use Refresh to try again, or return to your documents.";
    }
    if (lastItem && ["PENDING", "RUNNING"].includes(lastItem.processing.status) && Date.now() < deadline) timer = setTimeout(() => load(), 5000);
  } finally {
    loading = false;
    if (active) buttonBusy(refresh, false);
  }
}
if (guard()) {
  attachWorkspace();
  refresh.addEventListener("click", () => load(true));
  if (id) load();
  else {
    refresh.disabled = true;
    notice("Choose a document from your workspace to see its details.");
    document.getElementById("document-meta").textContent = "No document selected.";
  }
}
