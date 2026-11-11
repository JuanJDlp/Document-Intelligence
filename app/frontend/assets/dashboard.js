import {api, guard, notice} from "./api.js";
import {bytes, date, fileType, money} from "./format.js";
import {attachWorkspace, badge, buttonBusy, icon} from "./ui.js";

let items = [], cursor = null, timer = null, active = true, loading = false, loaded = false, uploading = false;
const accepted = new Map();
const controller = new AbortController();
const search = document.getElementById("search"), filter = document.getElementById("status-filter");
const input = document.getElementById("file"), uploadButton = document.getElementById("upload-submit");
const refreshButton = document.getElementById("refresh"), moreButton = document.getElementById("more");
window.addEventListener("docuprocess:leave", () => {
  active = false; clearTimeout(timer); controller.abort();
}, {once: true});

function mergeDocuments(...groups) {
  return [...new Map(groups.flat().map(item => [item.document_id, item])).values()]
    .sort((a, b) => b.created_at.localeCompare(a.created_at));
}
function state(title, description, retry = false, filtered = false) {
  document.getElementById("history-table").hidden = true;
  document.getElementById("history-state").hidden = false;
  document.getElementById("history-state-title").textContent = title;
  document.getElementById("history-state-description").textContent = description;
  document.getElementById("history-retry").hidden = !retry;
  document.getElementById("clear-filters").hidden = !filtered;
}
function schedule() {
  clearTimeout(timer);
  if (active && items.some(item => ["PENDING", "RUNNING"].includes(item.processing.status))) {
    timer = setTimeout(refreshProcessing, 10000);
  }
}
function render() {
  if (!loaded || !active) return;
  document.getElementById("stat-total").textContent = items.length;
  document.getElementById("stat-processing").textContent = items.filter(item => ["PENDING", "RUNNING"].includes(item.processing.status)).length;
  document.getElementById("stat-review").textContent = items.filter(item => ["PARTIAL", "FAILED"].includes(item.processing.status)).length;
  const query = search.value.trim().toLocaleLowerCase();
  const visible = items.filter(item => (!query || item.filename.toLocaleLowerCase().includes(query))
    && (filter.value === "ALL" || item.processing.status === filter.value));
  document.getElementById("history-count").textContent = visible.length + " of " + items.length + " loaded documents";
  moreButton.hidden = !cursor;
  const body = document.getElementById("history");
  body.replaceChildren();
  if (!items.length) {
    state("Your workspace starts here", "Upload your first receipt or invoice. Its progress and extracted details will appear here.");
  } else if (!visible.length) {
    state("No matching documents", "Try a different filename or status. Search covers the documents currently loaded.", false, true);
  } else {
    document.getElementById("history-state").hidden = true;
    document.getElementById("history-table").hidden = false;
    for (const item of visible) {
      const row = document.createElement("tr"), file = document.createElement("td");
      const fileCell = document.createElement("div"), fileIcon = document.createElement("span");
      fileCell.className = "file-cell"; fileIcon.className = "file-type-icon"; fileIcon.append(icon("document"));
      const copy = document.createElement("div"), link = document.createElement("a"), meta = document.createElement("small");
      copy.className = "file-copy";
      link.href = "document.html?id=" + encodeURIComponent(item.document_id);
      link.textContent = item.filename;
      meta.textContent = fileType(item.mime_type) + " · " + bytes(item.size_bytes);
      copy.append(link, meta); fileCell.append(fileIcon, copy); file.append(fileCell); row.append(file);
      const uploaded = document.createElement("td"), time = document.createElement("time");
      time.dateTime = item.created_at; time.textContent = date(item.created_at); uploaded.append(time);
      const status = document.createElement("td"); status.append(badge(item.processing.status));
      const total = document.createElement("td"); total.className = "table-amount"; total.textContent = item.result ? money(item.result) : "—";
      const action = document.createElement("td"), open = document.createElement("a");
      open.href = link.href; open.className = "row-link"; open.setAttribute("aria-label", "Open " + item.filename);
      open.append(icon("arrow-right")); action.append(open);
      row.append(uploaded, status, total, action); body.append(row);
    }
  }
  schedule();
}
async function load(more = false) {
  if (loading || !active) return;
  loading = true; clearTimeout(timer);
  buttonBusy(refreshButton, true, "Refreshing…"); moreButton.disabled = true;
  document.getElementById("history").setAttribute("aria-busy", "true");
  try {
    const result = await api("/documents" + (more && cursor ? "?cursor=" + encodeURIComponent(cursor) : ""), {signal: controller.signal});
    if (!active) return;
    result.items.forEach(item => accepted.delete(item.document_id));
    items = mergeDocuments(more ? items : [], result.items, [...accepted.values()]);
    cursor = result.next_cursor; loaded = true;
    render();
  } catch (error) {
    if (!active || error.name === "AbortError") return;
    if (!loaded) {
      state("We couldn’t load your documents", "Please check your connection, then try again.", true);
      document.getElementById("history-count").textContent = "Documents could not be loaded.";
    } else {
      notice("Your current documents are still shown. " + error.message, "info");
      render();
    }
  } finally {
    loading = false;
    if (active) {
      buttonBusy(refreshButton, false); moreButton.disabled = false;
      document.getElementById("history").setAttribute("aria-busy", "false");
      schedule();
    }
  }
}
async function refreshProcessing() {
  if (!active || loading) { schedule(); return; }
  try {
    const current = await Promise.all(items.filter(item => ["PENDING", "RUNNING"].includes(item.processing.status))
      .map(item => api("/documents/" + encodeURIComponent(item.document_id), {signal: controller.signal})));
    if (!active) return;
    items = mergeDocuments(items, current);
    current.forEach(item => { if (accepted.has(item.document_id)) accepted.set(item.document_id, item); });
    render();
  } catch (error) {
    if (!active || error.name === "AbortError") return;
    notice(error.message + " We’ll keep checking for updates.", "info");
    schedule();
  }
}
function fileError(file) {
  if (!file) return "Choose a file to continue.";
  if (!file.size) return "This file is empty. Choose a document with content.";
  if (file.size > 5242880) return "This file is too large. Choose a document up to 5 MiB.";
  const knownExtension = /\.(pdf|png|jpe?g)$/i.test(file.name);
  if (!["application/pdf", "image/png", "image/jpeg"].includes(file.type) && !(file.type === "" && knownExtension)) {
    return "Choose a PDF, PNG or JPEG document.";
  }
  return null;
}
function selectedFile(clearNotice = true) {
  const file = input.files[0], error = fileError(file);
  document.getElementById("selected-file").hidden = !file;
  document.getElementById("selected-name").textContent = file?.name || "";
  document.getElementById("selected-size").textContent = file ? bytes(file.size) : "";
  uploadButton.disabled = uploading || Boolean(error);
  if (clearNotice) notice(file && error ? error : "");
}

if (guard()) {
  attachWorkspace();
  load();
  search.addEventListener("input", render); filter.addEventListener("change", render);
  refreshButton.addEventListener("click", () => { notice(""); load(); });
  document.getElementById("history-retry").addEventListener("click", () => load());
  moreButton.addEventListener("click", () => load(true));
  document.getElementById("clear-filters").addEventListener("click", () => { search.value = ""; filter.value = "ALL"; render(); search.focus(); });
  input.addEventListener("change", () => selectedFile());
  document.getElementById("clear-file").addEventListener("click", () => { input.value = ""; selectedFile(); input.focus(); });
  const zone = document.getElementById("dropzone");
  zone.addEventListener("dragover", event => { event.preventDefault(); zone.classList.add("is-dragging"); });
  zone.addEventListener("dragleave", () => zone.classList.remove("is-dragging"));
  zone.addEventListener("drop", event => {
    event.preventDefault(); zone.classList.remove("is-dragging");
    if (uploading) return;
    if (event.dataTransfer.files.length !== 1) {
      input.value = ""; selectedFile(false); notice("Choose one document at a time."); return;
    }
    input.files = event.dataTransfer.files; selectedFile();
  });
  for (const name of ["dragover", "drop"]) document.addEventListener(name, event => {
    if ([...event.dataTransfer.types].includes("Files")) event.preventDefault();
  }, {signal: controller.signal});
  document.getElementById("upload").addEventListener("submit", async event => {
    event.preventDefault();
    if (uploading) return;
    const form = event.currentTarget;
    const error = fileError(input.files[0]);
    if (error) { notice(error); return; }
    const payload = new FormData(form);
    uploading = true;
    input.disabled = true;
    document.getElementById("clear-file").disabled = true;
    buttonBusy(uploadButton, true, "Uploading…"); notice("");
    try {
      const result = await api("/documents", {method: "POST", body: payload, signal: controller.signal});
      if (!active) return;
      const item = {...result, processing: {status: result.status, attempts: 0, last_error_code: null, updated_at: result.created_at}, result: null};
      accepted.set(item.document_id, item); items = mergeDocuments(items, [item]); loaded = true;
      search.value = ""; filter.value = "ALL"; render();
      form.reset(); selectedFile(false);
      notice("Document received. You can follow its progress below.", "success");
    } catch (error) {
      if (active && error.name !== "AbortError") notice(error.message);
    } finally {
      uploading = false; input.disabled = false; document.getElementById("clear-file")?.removeAttribute("disabled");
      buttonBusy(uploadButton, false);
      if (active) uploadButton.disabled = Boolean(fileError(input.files[0]));
    }
  });
}
