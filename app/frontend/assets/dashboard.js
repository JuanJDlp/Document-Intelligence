import {api, guard, notice, attachLogout} from "./api.js";
import {date, money} from "./format.js";
let items = [], cursor = null, timer = null, active = true;
window.addEventListener("docuprocess:leave", () => { active = false; clearTimeout(timer); }, {once:true});
function render() {
  const body = document.getElementById("history");
  body.replaceChildren();
  for (const item of items) {
    const row = document.createElement("tr");
    const file = document.createElement("td"), link = document.createElement("a");
    link.textContent = item.filename; link.href = "document.html?id=" + encodeURIComponent(item.document_id); file.append(link); row.append(file);
    for (const text of [date(item.created_at), item.processing.status, money(item.result)]) {
      const cell = document.createElement("td"); cell.textContent = text; row.append(cell);
    }
    body.append(row);
  }
  document.getElementById("more").hidden = !cursor;
  clearTimeout(timer);
  if (items.some(item => ["PENDING","RUNNING"].includes(item.processing.status))) timer = setTimeout(() => refresh().catch(error => notice(error.message)), 10000);
}
async function load(more) {
  const result = await api("/documents" + (more && cursor ? "?cursor=" + encodeURIComponent(cursor) : ""));
  if (!active) return;
  items = more ? [...items, ...result.items] : result.items; cursor = result.next_cursor; render();
}
if (guard()) {
  attachLogout();
  load(false).catch(error => notice(error.message));
  document.getElementById("more").addEventListener("click", () => load(true).catch(error => notice(error.message)));
  document.getElementById("upload").addEventListener("submit", async event => {
    event.preventDefault();
    const file = document.getElementById("file").files[0];
    if (!file || file.size > 5242880 || !["application/pdf","image/png","image/jpeg"].includes(file.type)) { notice("Choose a PDF, PNG or JPEG up to 5 MiB."); return; }
    const button = event.target.querySelector("button"); button.disabled = true;
    try {
      await api("/documents", {method:"POST", body:new FormData(event.target)});
      notice("Upload accepted. Processing is pending."); event.target.reset(); await load(false);
    } catch (error) { notice(error.message); }
    finally { button.disabled = false; }
  });
  document.querySelector("#upload button").disabled = false;
}

async function refresh() {
  const current = await Promise.all(items.map(item => api("/documents/" + encodeURIComponent(item.document_id))));
  if (!active) return;
  items = current; render();
}
