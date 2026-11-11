import {api, saveSession, notice, navigate} from "./api.js";
import {buttonBusy} from "./ui.js";

const tabs = [...document.querySelectorAll('[role="tab"]')];
function selectTab(id, focus = false) {
  for (const tab of tabs) {
    const selected = tab.id === id + "-tab";
    tab.setAttribute("aria-selected", String(selected));
    tab.tabIndex = selected ? 0 : -1;
    document.getElementById(tab.getAttribute("aria-controls")).hidden = !selected;
    if (selected && focus) tab.focus();
  }
  document.getElementById("auth-title").textContent = id === "login" ? "Welcome back." : "Make room for clarity.";
  document.getElementById("auth-description").textContent = id === "login"
    ? "Sign in to pick up where you left off." : "Create your account and bring your documents together.";
  notice("");
}
for (const tab of tabs) tab.addEventListener("click", () => selectTab(tab.id.replace("-tab", "")));
document.querySelector('[role="tablist"]').addEventListener("keydown", event => {
  if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
  event.preventDefault();
  const index = tabs.indexOf(document.activeElement);
  const next = event.key === "Home" ? 0 : event.key === "End" ? tabs.length - 1
    : (index + (event.key === "ArrowRight" ? 1 : -1) + tabs.length) % tabs.length;
  selectTab(tabs[next].id.replace("-tab", ""), true);
});
for (const toggle of document.querySelectorAll("[data-password]")) {
  toggle.addEventListener("click", () => {
    const input = document.getElementById(toggle.dataset.password);
    const visible = input.type === "password";
    input.type = visible ? "text" : "password";
    toggle.setAttribute("aria-pressed", String(visible));
    toggle.setAttribute("aria-label", visible ? "Hide password" : "Show password");
  });
}
for (const id of ["login", "register"]) {
  const form = document.getElementById(id);
  const button = form.querySelector('[type="submit"]');
  button.disabled = false;
  form.addEventListener("submit", async event => {
    event.preventDefault();
    notice("");
    buttonBusy(button, true, id === "login" ? "Signing in…" : "Creating account…");
    try {
      const values = Object.fromEntries(new FormData(form));
      const body = {email: values.email.trim(), password: values.password};
      if (id === "register") {
        body.full_name = values.full_name.trim();
        if (!body.full_name) throw new Error("Please enter your name.");
        if (body.password.length < 12 || body.password.length > 128 || !/[A-Za-z]/.test(body.password) || !/[0-9]/.test(body.password)) {
          throw new Error("Use 12–128 characters, with at least one letter and one number.");
        }
        await api("/auth/register", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
        form.reset();
        selectTab("login");
        document.getElementById("email").value = body.email;
        document.getElementById("password").focus();
        notice("Your account is ready. Sign in to open your workspace.", "success");
      } else {
        const result = await api("/auth/login", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify(body)});
        saveSession(result);
        await navigate("dashboard.html");
      }
    } catch (error) { notice(error.message); }
    finally { buttonBusy(button, false); }
  });
}
const reason = new URLSearchParams(location.search).get("reason");
if (reason === "expired") notice("Your session expired. Please sign in again.", "info");
if (reason === "signed-out") notice("You’ve signed out. See you next time.", "success");
