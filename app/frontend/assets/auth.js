import {api, saveSession, notice, navigate} from "./api.js";
for (const id of ["login", "register"]) {
  document.getElementById(id).addEventListener("submit", async event => {
    event.preventDefault();
    const button = event.target.querySelector("button");
    button.disabled = true;
    try {
      const body = Object.fromEntries(new FormData(event.target));
      if (id === "register") {
        if (!/[A-Za-z]/.test(body.password) || !/[0-9]/.test(body.password)) throw new Error("Include a letter and a number in your password.");
        await api("/auth/register", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
        notice("Account created. You can now sign in.");
        event.target.reset();
      } else {
        const result = await api("/auth/login", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify(body)});
        saveSession(result);
        await navigate("dashboard.html");
      }
    } catch (error) { notice(error.message); }
    finally { button.disabled = false; }
  });
  document.getElementById(id).querySelector("button").disabled = false;
}

if (new URLSearchParams(location.search).get("reason") === "expired") notice("Your session expired. Please sign in again.");
