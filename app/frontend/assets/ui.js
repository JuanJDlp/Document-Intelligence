import {api, attachLogout} from "./api.js";
import {label, confidence} from "./format.js";

export function icon(name, className = "icon") {
  const node = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  node.setAttribute("class", className);
  node.setAttribute("aria-hidden", "true");
  node.setAttribute("focusable", "false");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", "assets/icons.svg#" + name);
  node.append(use);
  return node;
}
export const statuses = {
  PENDING: "Pending", RUNNING: "Processing", COMPLETED: "Completed",
  PARTIAL: "Needs review", FAILED: "Failed",
};
export function badge(state) {
  const node = document.createElement("span");
  node.className = "status-badge";
  node.dataset.state = state;
  node.textContent = statuses[state] || "Unknown status";
  return node;
}
export function buttonBusy(button, busy, message) {
  const text = button.querySelector("span");
  if (text && !button.dataset.label) button.dataset.label = text.textContent;
  if (!text && !button.dataset.label) button.dataset.label = button.textContent.trim();
  button.disabled = busy;
  button.setAttribute("aria-busy", String(busy));
  if (text) text.textContent = busy ? message : button.dataset.label;
}
export function attachWorkspace() {
  attachLogout();
  const controller = new AbortController();
  window.addEventListener("docuprocess:leave", () => controller.abort(), {once: true});
  api("/me", {signal: controller.signal}).then(user => {
    if (controller.signal.aborted) return;
    document.getElementById("account-name").textContent = user.full_name;
    document.getElementById("account-role").textContent = user.role === "admin" ? "Administrator" : "Personal workspace";
    document.getElementById("account-avatar").textContent = user.full_name.trim().slice(0, 1).toUpperCase() || "·";
  }).catch(() => { /* The document request handles connection feedback; 401 redirects centrally. */ });
}
export function confidenceFields(root, values) {
  root.replaceChildren();
  for (const [field, value] of Object.entries(values)) {
    const row = document.createElement("div");
    row.className = "confidence-entry";
    const title = document.createElement("span"), amount = document.createElement("strong");
    title.textContent = label(field);
    amount.textContent = confidence(value);
    row.append(title, amount);
    if (typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 1) {
      const meter = document.createElement("meter");
      meter.min = 0; meter.max = 1; meter.value = value;
      meter.setAttribute("aria-label", label(field) + ": " + confidence(value));
      row.append(meter);
    }
    root.append(row);
  }
}
