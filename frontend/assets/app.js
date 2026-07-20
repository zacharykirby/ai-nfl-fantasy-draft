const state = { cockpit: null, position: "ALL", session: null };

const byId = (id) => document.getElementById(id);

async function api(path) {
  const response = await fetch(path, { headers: { Accept: "application/json" } });
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || `Request failed (${response.status})`);
  return payload;
}

function playerRow(player) {
  return `<div class="player-row">
    <div>
      <div class="player-name">${escapeHtml(player.player)}</div>
      <div class="player-detail">${escapeHtml(player.position)} · ${escapeHtml(player.team || "FA")} · Tier ${player.tier ?? "—"}</div>
    </div>
    <div class="rank-badge">${escapeHtml(player.position)}${player.position_rank ?? "—"}</div>
  </div>`;
}

function compactRow(left, right = "") {
  return `<div class="compact-row"><span>${escapeHtml(left)}</span><span class="player-detail">${escapeHtml(right)}</span></div>`;
}

function setList(element, html, emptyText) {
  element.innerHTML = html || emptyText;
  element.classList.toggle("empty-state", !html);
}

function render(cockpit) {
  state.cockpit = cockpit;
  const session = cockpit.session;
  byId("session-name").textContent = session.name;
  byId("round").textContent = session.round;
  byId("current-pick").textContent = session.current_pick;
  byId("your-turn").textContent = session.picks_until_user === 0 ? "Now" : session.picks_until_user ?? "Done";
  byId("available-count").textContent = `${session.available} available`;

  const recommendation = cockpit.recommendation;
  const primary = recommendation?.primary;
  byId("primary-player").textContent = primary?.player || "Draft complete";
  byId("primary-meta").textContent = primary
    ? `${primary.position}${primary.position_rank} · ${primary.team || "FA"} · Tier ${primary.tier} · ${Number(primary.vorp || 0).toFixed(1)} VORP`
    : "No active recommendation";
  byId("confidence").textContent = recommendation ? `${Math.round(recommendation.confidence * 100)}%` : "—";
  byId("mode").textContent = recommendation?.mode || "complete";
  byId("primary-reasons").innerHTML = (primary?.reasons || []).slice(0, 3)
    .map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");

  setList(
    byId("alternatives"),
    (recommendation?.alternatives || []).slice(0, 3).map(playerRow).join(""),
    "No alternatives available",
  );
  renderAvailable();
  setList(
    byId("roster"),
    cockpit.user_roster.map((player) => compactRow(player.player, player.position)).join(""),
    "No picks yet",
  );
  setList(
    byId("tier-alerts"),
    cockpit.tier_alerts.map((alert) => compactRow(`${alert.position} Tier ${alert.tier}`, `${alert.remaining} left`)).join(""),
    "No urgent drops",
  );
  setList(
    byId("recent-picks"),
    cockpit.recent_picks.slice().reverse().map((pick) => compactRow(`${pick.overall_pick}. ${pick.player}`, `${pick.position} · Team ${pick.team}`)).join(""),
    "No selections yet",
  );
  byId("health").textContent = `${cockpit.health.board} · ${cockpit.health.model}`;
}

function renderAvailable() {
  if (!state.cockpit) return;
  const players = state.position === "ALL"
    ? state.cockpit.best_available
    : state.cockpit.top_available_by_position[state.position] || [];
  setList(byId("best-available"), players.map(playerRow).join(""), "No players available");
}

async function load() {
  showError("");
  const sessions = await api("/api/v1/sessions");
  const requested = new URLSearchParams(window.location.search).get("session");
  state.session = requested || sessions.sessions[0]?.name;
  if (!state.session) throw new Error("No saved draft sessions were found.");
  const cockpit = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/cockpit`);
  render(cockpit);
}

function showError(message) {
  const notice = byId("notice");
  notice.hidden = !message;
  notice.textContent = message;
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

byId("refresh").addEventListener("click", () => load().catch((error) => showError(error.message)));
document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.position = button.dataset.position;
    renderAvailable();
  });
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") load().catch((error) => showError(error.message));
});

load().catch((error) => showError(error.message));
