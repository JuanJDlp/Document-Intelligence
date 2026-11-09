const base = "/api/v1";
let inMemory = null;
export function session() {
  try { return JSON.parse(sessionStorage.getItem("session")) || inMemory; } catch { return inMemory; }
}
export function saveSession(value) {
  inMemory = value;
  try { if (value) sessionStorage.setItem("session", JSON.stringify(value)); else sessionStorage.removeItem("session"); } catch { /* Per-tab memory remains usable. */ }
}
export function guard() {
  const value = session();
  if (!value || Date.parse(value.expires_at) <= Date.now()) {
    saveSession(null); location.replace("index.html?reason=expired"); return false;
  }
  return true;
}
export async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  const value = session();
  if (value) headers.set("Authorization", "Bearer " + value.token);
  const response = await fetch(base + path, {...options, headers});
  if (response.status === 401 && !path.startsWith("/auth/")) {
    saveSession(null); location.replace("index.html?reason=expired");
  }
  if (response.status === 204) return null;
  let result;
  try { result = await response.json(); } catch { throw new Error("The service returned an unreadable response."); }
  if (!response.ok) throw new Error(result.error?.message || "Request failed.");
  return result;
}
export function notice(message) { const target = document.getElementById("notice"); if (target) target.textContent = message; }
export function attachLogout() {
  document.getElementById("logout").addEventListener("click", async () => {
    try { await api("/auth/logout", {method:"POST"}); } catch { /* Clear local session regardless. */ }
    saveSession(null); location.replace("index.html?reason=expired");
  });
}

let viewCounter = 0;
let memoryNavigation = false;
export async function navigate(path, push = true) {
  let stored = false;
  try { stored = Boolean(sessionStorage.getItem("session")); } catch { /* In-memory fallback. */ }
  if (stored || !inMemory) { location.assign(path); return; }
  const url = new URL(path, location.href);
  if (url.origin !== location.origin || !url.pathname.endsWith(".html")) throw new Error("Invalid local page.");
  const response = await fetch(url);
  if (!response.ok) throw new Error("The page could not be loaded.");
  const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
  const script = parsed.querySelector('script[type="module"]');
  const source = script?.getAttribute("src");
  parsed.querySelectorAll("script").forEach(node => node.remove());
  window.dispatchEvent(new Event("docuprocess:leave"));
  document.title = parsed.title;
  document.body.replaceChildren(...parsed.body.childNodes);
  if (push) history.pushState(null, "", url);
  memoryNavigation = true;
  if (source) await import(new URL(source, url).href + "?view=" + (++viewCounter));
  document.querySelector("h1")?.setAttribute("tabindex", "-1");
  document.querySelector("h1")?.focus();
}
document.addEventListener("click", event => {
  if (!memoryNavigation || event.ctrlKey || event.metaKey || event.shiftKey) return;
  const link = event.target.closest("a");
  if (link && new URL(link.href).origin === location.origin && new URL(link.href).pathname.endsWith(".html")) {
    event.preventDefault(); navigate(link.href).catch(error => notice(error.message));
  }
});
window.addEventListener("popstate", () => {
  if (memoryNavigation) navigate(location.href, false).catch(error => notice(error.message));
});
