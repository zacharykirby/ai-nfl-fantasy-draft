const state = {
  cockpit: null,
  position: "ALL",
  session: null,
  pendingPick: null,
  pendingUndo: null,
  pendingBulk: null,
};

const byId = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { Accept: "application/json", ...(options.headers || {}) },
  });
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
  byId("undo-last").disabled = cockpit.recent_picks.length === 0;
}

function renderAvailable() {
  if (!state.cockpit) return;
  const players = state.position === "ALL"
    ? state.cockpit.best_available
    : state.cockpit.top_available_by_position[state.position] || [];
  setList(byId("best-available"), players.map(playerRow).join(""), "No players available");
}

async function load() {
  showNotice("");
  const sessions = await api("/api/v1/sessions");
  const requested = new URLSearchParams(window.location.search).get("session");
  state.session = requested || sessions.sessions[0]?.name;
  if (!state.session) throw new Error("No saved draft sessions were found.");
  const cockpit = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/cockpit`);
  render(cockpit);
}

function showNotice(message, success = false) {
  const notice = byId("notice");
  notice.hidden = !message;
  notice.textContent = message;
  notice.classList.toggle("success", Boolean(message) && success);
}

async function interpretCommand(text) {
  return api(`/api/v1/sessions/${encodeURIComponent(state.session)}/commands/interpret`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

function requestId() {
  if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID();
  return `web-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

async function recordPendingPick() {
  if (!state.pendingPick) return;
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/picks`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      player: state.pendingPick.player.player,
      request_id: state.pendingPick.requestId,
      mode: "balanced",
    }),
  });
  render(result.cockpit);
  byId("command-input").value = "";
  state.pendingPick = null;
  showNotice(`Recorded ${result.event.player} at pick ${result.event.overall_pick}.`, true);
}

async function previewBulk(text) {
  return api(`/api/v1/sessions/${encodeURIComponent(state.session)}/picks/bulk/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text }),
  });
}

async function recordPendingBulk() {
  if (!state.pendingBulk) return;
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/picks/bulk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      players: state.pendingBulk.picks.map((pick) => pick.player),
      expected_start_pick: state.pendingBulk.start_pick,
      request_id: state.pendingBulk.requestId,
      mode: "balanced",
    }),
  });
  render(result.cockpit);
  byId("catch-up-input").value = "";
  const count = result.events.length;
  state.pendingBulk = null;
  showNotice(`Recorded ${count} catch-up picks.`, true);
}

async function undoPendingPick() {
  if (!state.pendingUndo) return;
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/undo`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      request_id: state.pendingUndo.requestId,
      target_event_id: state.pendingUndo.pick.event_id,
      mode: "balanced",
    }),
  });
  render(result.cockpit);
  state.pendingUndo = null;
  showNotice(`Restored ${result.event.player} to the available pool.`, true);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>'"]/g, (char) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;",
  })[char]);
}

byId("refresh").addEventListener("click", () => load().catch((error) => showNotice(error.message)));
byId("undo-last").addEventListener("click", () => {
  const picks = state.cockpit?.recent_picks || [];
  const pick = picks[picks.length - 1];
  if (!pick) return;
  state.pendingUndo = { pick, requestId: requestId() };
  byId("undo-player").textContent = pick.player;
  byId("undo-text").textContent = `Undo pick ${pick.overall_pick} (${pick.position}) for Team ${pick.team}?`;
  byId("undo-dialog").returnValue = "";
  byId("undo-dialog").showModal();
});
byId("catch-up").addEventListener("click", () => {
  byId("catch-up-dialog").returnValue = "";
  byId("catch-up-dialog").showModal();
  byId("catch-up-input").focus();
});
document.querySelectorAll(".filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.position = button.dataset.position;
    renderAvailable();
  });
});
document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible") load().catch((error) => showNotice(error.message));
});

byId("command-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = byId("command-input");
  const send = byId("command-send");
  const text = input.value.trim();
  if (!text) return;
  send.disabled = true;
  showNotice("");
  try {
    const interpretation = await interpretCommand(text);
    if (interpretation.intent !== "record_pick") {
      showNotice(interpretation.message);
      return;
    }
    state.pendingPick = { ...interpretation, requestId: requestId() };
    byId("confirmation-player").textContent = interpretation.player.player;
    byId("confirmation-text").textContent = interpretation.confirmation.text;
    byId("confirmation-dialog").returnValue = "";
    byId("confirmation-dialog").showModal();
  } catch (error) {
    showNotice(error.message);
  } finally {
    send.disabled = false;
  }
});

byId("confirmation-dialog").addEventListener("close", async () => {
  if (byId("confirmation-dialog").returnValue !== "confirm") {
    state.pendingPick = null;
    return;
  }
  try {
    await recordPendingPick();
  } catch (error) {
    showNotice(error.message);
  }
});

byId("undo-dialog").addEventListener("close", async () => {
  if (byId("undo-dialog").returnValue !== "confirm") {
    state.pendingUndo = null;
    return;
  }
  try {
    await undoPendingPick();
  } catch (error) {
    state.pendingUndo = null;
    showNotice(error.message);
  }
});

byId("catch-up-dialog").addEventListener("close", async () => {
  if (byId("catch-up-dialog").returnValue !== "preview") return;
  const text = byId("catch-up-input").value.trim();
  if (!text) return;
  try {
    const preview = await previewBulk(text);
    state.pendingBulk = { ...preview, requestId: requestId() };
    byId("bulk-title").textContent = `${preview.picks.length} picks · ${preview.start_pick}–${preview.end_pick}`;
    byId("bulk-preview").innerHTML = preview.picks.map((pick) => compactRow(
      `${pick.overall_pick}. ${pick.player}`,
      `${pick.position} · Team ${pick.team}`,
    )).join("");
    byId("bulk-confirmation-dialog").returnValue = "";
    byId("bulk-confirmation-dialog").showModal();
  } catch (error) {
    showNotice(error.message);
  }
});

byId("bulk-confirmation-dialog").addEventListener("close", async () => {
  if (byId("bulk-confirmation-dialog").returnValue !== "confirm") {
    state.pendingBulk = null;
    return;
  }
  try {
    await recordPendingBulk();
  } catch (error) {
    state.pendingBulk = null;
    showNotice(error.message);
  }
});

load().catch((error) => showNotice(error.message));
