const base = "/api/v1";
let inMemory = null;

function validSession(value) {
  return value && typeof value.token === "string" && value.token.length > 0
    && typeof value.expires_at === "string" && Number.isFinite(Date.parse(value.expires_at));
}
export function session() {
  try {
    const stored = JSON.parse(sessionStorage.getItem("session"));
    if (validSession(stored)) return stored;
  } catch { /* A per-tab memory session remains available when storage is blocked. */ }
  return validSession(inMemory) ? inMemory : null;
}
export function saveSession(value) {
  inMemory = validSession(value) ? value : null;
  try {
    if (inMemory) sessionStorage.setItem("session", JSON.stringify(inMemory));
    else sessionStorage.removeItem("session");
  } catch { /* Storage is optional. */ }
}
export function guard() {
  const value = session();
  if (!value || Date.parse(value.expires_at) <= Date.now()) {
    saveSession(null);
    location.replace("index.html?reason=expired");
    return false;
  }
  return true;
}
export async function api(path, options = {}) {
  const headers = new Headers(options.headers);
  const value = session();
  if (value) headers.set("Authorization", "Bearer " + value.token);
  let response;
  try {
    response = await fetch(base + path, {...options, headers});
  } catch (error) {
    if (error.name === "AbortError") throw error;
    throw new Error("We couldn’t reach the service. Check your connection and try again.");
  }
  if (response.status === 401 && !path.startsWith("/auth/")) {
    saveSession(null);
    location.replace("index.html?reason=expired");
  }
  if (response.status === 204) return null;
  let result;
  try { result = await response.json(); }
  catch { throw new Error("The service returned an unreadable response. Please try again."); }
  if (!response.ok) throw new Error(result.error?.message || "The request could not be completed.");
  return result;
}
export function notice(message = "", kind = "error") {
  const target = document.getElementById("notice");
  if (!target) return;
  target.textContent = message;
  target.hidden = !message;
  target.className = "notice notice--" + (["error", "success", "info"].includes(kind) ? kind : "error");
  target.setAttribute("role", kind === "error" ? "alert" : "status");
  target.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
}
export function attachLogout() {
  const button = document.getElementById("logout");
  if (!button) return;
  button.addEventListener("click", async event => {
    event.currentTarget.disabled = true;
    try { await api("/auth/logout", {method: "POST"}); }
    catch { /* Clear local state even if the server is unreachable. */ }
    saveSession(null);
    location.replace("index.html?reason=signed-out");
  });
  button.disabled = false;
}

let viewCounter = 0;
let navigationSequence = 0;
let memoryNavigation = false;
export async function navigate(path, push = true) {
  const url = new URL(path, location.href);
  if (url.origin !== location.origin || !["index.html", "dashboard.html", "document.html"].some(name => url.pathname.endsWith("/" + name))) {
    throw new Error("Invalid workspace page.");
  }
  let stored = false;
  try { stored = Boolean(sessionStorage.getItem("session")); } catch { /* Memory navigation. */ }
  if (stored || !inMemory) { location.assign(url); return; }
  const sequence = ++navigationSequence;
  const response = await fetch(url);
  if (!response.ok) throw new Error("The page could not be loaded. Please try again.");
  const parsed = new DOMParser().parseFromString(await response.text(), "text/html");
  if (sequence !== navigationSequence) return;
  const source = parsed.querySelector('script[type="module"]')?.getAttribute("src");
  parsed.querySelectorAll("script").forEach(node => node.remove());
  window.dispatchEvent(new Event("docuprocess:leave"));
  document.title = parsed.title;
  document.body.className = parsed.body.className;
  document.body.replaceChildren(...parsed.body.childNodes);
  if (push) history.pushState(null, "", url);
  memoryNavigation = true;
  if (source) await import(new URL(source, url).href + "?view=" + (++viewCounter));
  const heading = document.querySelector("h1");
  heading?.setAttribute("tabindex", "-1");
  heading?.focus({preventScroll: true});
  if (url.hash) document.getElementById(decodeURIComponent(url.hash.slice(1)))?.scrollIntoView();
  else window.scrollTo(0, 0);
}
document.addEventListener("click", event => {
  if (!memoryNavigation || event.defaultPrevented || event.button !== 0 || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
  const link = event.target instanceof Element ? event.target.closest("a[href]") : null;
  if (!link || link.target || link.hasAttribute("download")) return;
  const url = new URL(link.href);
  if (url.origin !== location.origin || !url.pathname.endsWith(".html")) return;
  if (url.pathname === location.pathname && url.search === location.search && url.hash) return;
  event.preventDefault();
  navigate(link.href).catch(error => notice(error.message));
});
window.addEventListener("popstate", () => {
  if (memoryNavigation) navigate(location.href, false).catch(error => notice(error.message));
});
