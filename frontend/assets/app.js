const state = {
  cockpit: null,
  position: "ALL",
  session: null,
  pendingPick: null,
  pendingUndo: null,
  pendingBulk: null,
  askController: null,
  sessions: [],
  board: null,
  createRequestId: null,
  pendingDelete: null,
  view: "cockpit",
  boardPosition: "ALL",
  detailPlayer: null,
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
  const teamSelect = byId("log-team");
  const selectedTeam = teamSelect.value;
  teamSelect.innerHTML = `<option value="">All teams</option>${Array.from(
    { length: Number(cockpit.league.league_size) },
    (_item, index) => `<option value="${index + 1}">Team ${index + 1}</option>`,
  ).join("")}`;
  teamSelect.value = selectedTeam;
  if (state.view !== "cockpit") {
    queueMicrotask(() => refreshActiveView().catch((error) => showNotice(error.message)));
  }
}

function renderAvailable() {
  if (!state.cockpit) return;
  const players = state.position === "ALL"
    ? state.cockpit.best_available
    : state.cockpit.top_available_by_position[state.position] || [];
  setList(byId("best-available"), players.map(playerRow).join(""), "No players available");
}

async function showView(view) {
  state.view = view;
  document.querySelectorAll(".view-panel").forEach((panel) => {
    panel.hidden = panel.id !== `view-${view}`;
  });
  document.querySelectorAll(".view-tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === view);
  });
  await refreshActiveView();
}

async function refreshActiveView() {
  if (!state.session || state.view === "cockpit") return;
  if (state.view === "board") await loadBoardView();
  if (state.view === "roster") await loadRosterView();
  if (state.view === "log") await loadDraftLogView();
}

async function loadBoardView() {
  byId("full-board").innerHTML = `<div class="view-loading">Loading board…</div>`;
  const position = state.boardPosition === "ALL" ? "" : `&position=${state.boardPosition}`;
  const available = byId("board-available-only").checked;
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/board?available_only=${available}${position}`);
  const html = Object.entries(result.positions).map(([role, group]) => {
    const tiers = group.tiers.map((tier) => `<section class="tier-section">
      <div class="tier-heading"><span>Tier ${tier.tier === 99 ? "—" : tier.tier}</span><span>${tier.count} player${tier.count === 1 ? "" : "s"}</span></div>
      ${tier.players.map((player) => `<button class="board-player ${player.available ? "" : "drafted"}" type="button" data-player-id="${escapeHtml(player.player_id)}">
        ${playerRow(player)}
      </button>`).join("")}
    </section>`).join("");
    return `<div class="position-heading"><h2>${role}</h2><span class="small-meta">${group.count} shown</span></div>${tiers || `<div class="card empty-state">No ${role} players match.</div>`}`;
  }).join("");
  byId("full-board").innerHTML = html || `<div class="card empty-state">No players match this board filter.</div>`;
}

async function loadRosterView() {
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/roster`);
  byId("roster-title").textContent = `Team ${result.team} · ${result.players.length} selections`;
  byId("roster-needs").innerHTML = ["QB", "RB", "WR", "TE"].map((position) => {
    const need = result.needs[position];
    return `<div class="need-card ${need.open_base_slots ? "open" : ""}"><strong>${position}</strong><span>${need.rostered}/${need.base_starters} · ${need.open_base_slots} open</span></div>`;
  }).join("");
  byId("bye-status").textContent = result.bye_summary.conflict_count
    ? `${result.bye_summary.conflict_count} conflict${result.bye_summary.conflict_count === 1 ? "" : "s"}`
    : "No conflicts";
  setList(
    byId("bye-summary"),
    result.bye_summary.weeks.map((item) => compactRow(
      `Week ${item.week}${item.conflict ? " · conflict" : ""}`,
      item.players.join(", "),
    )).join("") + (result.bye_summary.missing.length
      ? compactRow("Bye unknown", result.bye_summary.missing.join(", ")) : ""),
    "No rostered bye weeks yet",
  );
  byId("roster-count").textContent = `${result.players.length} player${result.players.length === 1 ? "" : "s"}`;
  setList(
    byId("roster-detail-list"),
    result.players.map((player) => `<button class="clickable-row" type="button" data-player-id="${escapeHtml(player.player_id)}">${playerRow(player)}<span class="player-detail">Pick ${player.drafted_at.overall_pick} · Round ${player.drafted_at.round}</span></button>`).join(""),
    "No selections yet",
  );
}

async function loadDraftLogView() {
  const params = new URLSearchParams();
  if (byId("log-team").value) params.set("team", byId("log-team").value);
  if (byId("log-position").value) params.set("position", byId("log-position").value);
  const suffix = params.toString() ? `?${params}` : "";
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/draft-log${suffix}`);
  byId("log-count").textContent = result.count;
  setList(
    byId("draft-log-list"),
    result.picks.slice().reverse().map((pick) => `<button class="clickable-row log-pick ${pick.status}" type="button" data-player-id="${escapeHtml(pick.player_id)}">${compactRow(
      `${pick.overall_pick}. ${pick.player}${pick.status === "undone" ? " · UNDONE" : ""}`,
      `${pick.position} · Team ${pick.team} · Round ${pick.round}`,
    )}</button>`).join(""),
    "No picks recorded",
  );
}

async function openPlayerDetail(playerId) {
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/players/${encodeURIComponent(playerId)}`);
  const player = result.player;
  state.detailPlayer = player;
  byId("player-detail-position").textContent = `${player.position}${player.position_rank || ""} · ${player.team || "FA"}`;
  byId("player-detail-name").textContent = player.player;
  byId("player-detail-meta").textContent = player.available
    ? `Available at pick ${result.current_pick}`
    : `Drafted at pick ${player.drafted.overall_pick} by Team ${player.drafted.team}`;
  const stats = [
    [player.projected_points ?? "—", "Projected"],
    [player.vorp ?? "—", "VORP"],
    [player.adp ?? "—", "ADP"],
    [player.tier ?? "—", "Tier"],
    [player.bye_week ?? "—", "Bye"],
    [player.age ?? "—", "Age"],
  ];
  byId("player-detail-stats").innerHTML = stats.map(([value, label]) => `<div class="detail-stat"><strong>${escapeHtml(value)}</strong><span>${label}</span></div>`).join("");
  const evidence = player.evidence || {};
  const evidenceRows = [
    ["Projection", player.projection_method || "unknown"],
    ["Projection source", player.projection_source || "unknown"],
    ["Historical points", evidence.weighted_historical_points ?? "—"],
    ["Historical PPG", evidence.weighted_historical_points_per_game ?? "—"],
    ["Availability rate", evidence.historical_availability_rate != null ? `${Math.round(evidence.historical_availability_rate * 100)}%` : "—"],
    ["Risk", player.risk?.level || "Unknown"],
    ["Flags", (player.flags || []).join(", ") || "None"],
  ];
  byId("player-detail-evidence").innerHTML = evidenceRows.map(([label, value]) => `<div class="evidence-row"><span>${escapeHtml(label)}</span><strong>${escapeHtml(value)}</strong></div>`).join("");
  byId("player-detail-draft").hidden = !player.available;
  if (!byId("player-detail-dialog").open) byId("player-detail-dialog").showModal();
}

function savedSession() {
  try { return localStorage.getItem("draft-cockpit-session"); } catch (_error) { return null; }
}

function rememberSession(name) {
  try { localStorage.setItem("draft-cockpit-session", name); } catch (_error) { /* private mode */ }
}

function forgetSession(name) {
  try {
    if (localStorage.getItem("draft-cockpit-session") === name) {
      localStorage.removeItem("draft-cockpit-session");
    }
  } catch (_error) { /* private mode */ }
}

async function load(preferredSession = null) {
  showNotice("");
  const [sessions, board] = await Promise.all([
    api("/api/v1/sessions"),
    api("/api/v1/board/summary"),
  ]);
  state.sessions = sessions.sessions;
  state.board = board;
  renderSessionManager();
  const requested = new URLSearchParams(window.location.search).get("session");
  const availableNames = new Set(state.sessions.map((session) => session.name));
  const selected = [preferredSession, requested, savedSession(), state.sessions[0]?.name]
    .find((name) => name && availableNames.has(name));
  if (!selected) {
    state.session = null;
    byId("command-input").disabled = true;
    byId("command-send").disabled = true;
    openSessionManager(true);
    showNotice("Create a draft session to get started.");
    return;
  }
  await loadSession(selected);
}

async function loadSession(name) {
  const cockpit = await api(`/api/v1/sessions/${encodeURIComponent(name)}/cockpit`);
  state.session = name;
  byId("command-input").disabled = false;
  byId("command-send").disabled = false;
  rememberSession(name);
  const url = new URL(window.location.href);
  url.searchParams.set("session", name);
  history.replaceState(null, "", url);
  byId("assistant-card").hidden = true;
  render(cockpit);
  renderSessionManager();
  if (byId("session-dialog").open) byId("session-dialog").close();
}

function sessionSlug(value) {
  return String(value || "").trim().toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);
}

function boardPlayerCount() {
  return Object.values(state.board?.role_counts || {}).reduce((total, count) => total + Number(count || 0), 0);
}

function updateSessionCapacity() {
  const teams = Number(byId("new-league-size").value || 0);
  const total = boardPlayerCount();
  const maxRounds = teams ? Math.min(30, Math.floor(total / teams)) : 0;
  byId("new-rounds").max = Math.max(1, maxRounds);
  if (Number(byId("new-rounds").value) > maxRounds) byId("new-rounds").value = maxRounds;
  byId("new-user-team").max = Math.max(1, teams);
  if (Number(byId("new-user-team").value) > teams) byId("new-user-team").value = teams;
  byId("new-session-capacity").textContent = `${total} ranked players · up to ${maxRounds} rounds for ${teams || "—"} teams`;
  byId("create-session").disabled = state.board?.health?.status !== "ready" || maxRounds < 1;
}

function renderSessionManager() {
  setList(
    byId("session-list"),
    state.sessions.map((session) => `<div class="session-row">
      <button class="session-option" type="button" data-session="${escapeHtml(session.name)}">
        <span><strong>${escapeHtml(session.name)}</strong><span class="session-meta">${escapeHtml(session.status)} · Pick ${session.current_pick} · Slot ${session.user_team}</span></span>
        <span class="resume-label">${session.name === state.session ? "Current" : "Resume"}</span>
      </button>
      <button class="session-delete" type="button" data-delete-session="${escapeHtml(session.name)}" aria-label="Delete ${escapeHtml(session.name)}">⌫</button>
    </div>`).join(""),
    "No saved drafts yet",
  );
  const leagueSize = Number(state.board?.league?.league_size || 10);
  const total = boardPlayerCount();
  if (!byId("new-league-size").value) byId("new-league-size").value = leagueSize;
  if (!byId("new-rounds").value) byId("new-rounds").value = Math.min(15, Math.floor(total / leagueSize));
  if (!byId("new-user-team").value) byId("new-user-team").value = 1;
  const ready = state.board?.health?.status === "ready";
  byId("session-board-status").textContent = ready ? "Board ready" : "Board not ready";
  updateSessionCapacity();
}

function openSessionManager(required = false) {
  byId("session-dialog-close").hidden = required;
  if (!byId("session-dialog").open) byId("session-dialog").showModal();
}

function showSessionNotice(message, success = false) {
  const notice = byId("session-form-notice");
  notice.hidden = !message;
  notice.textContent = message;
  notice.classList.toggle("success", Boolean(message) && success);
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

async function askAssistant(question) {
  const controller = new AbortController();
  state.askController = controller;
  byId("assistant-cancel").hidden = false;
  showNotice("Asking the draft assistant…");
  try {
    const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/assistant/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode: "balanced" }),
      signal: controller.signal,
    });
    renderAssistant(question, result);
    byId("command-input").value = "";
    if (result.freshness.stale) {
      showNotice("The draft changed while that answer was in flight. State refreshed; ask again for current advice.");
      const cockpit = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/cockpit`);
      render(cockpit);
    } else {
      showNotice("Answer ready.", true);
    }
  } finally {
    if (state.askController === controller) state.askController = null;
    byId("assistant-cancel").hidden = true;
  }
}

function renderAssistant(question, result) {
  const answer = result.answer;
  const stale = Boolean(result.freshness.stale);
  const source = answer.source === "model" ? "MODEL" : "LOCAL FALLBACK";
  const card = byId("assistant-card");
  card.hidden = false;
  card.classList.toggle("stale", stale);
  byId("assistant-question").textContent = question;
  byId("assistant-source").textContent = `${stale ? "STALE · " : ""}${source} · ${result.latency_ms}ms`;
  byId("assistant-answer").textContent = answer.answer;
  byId("assistant-recommendation").textContent = stale
    ? `Previous recommendation: ${answer.recommendation || "none"} — ask again`
    : answer.recommendation ? `Recommendation: ${answer.recommendation}` : "No single-player recommendation";
  byId("assistant-rationale").innerHTML = (answer.rationale || []).slice(0, 4)
    .map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  byId("assistant-cautions").innerHTML = (answer.cautions || []).slice(0, 3)
    .map((item) => `<li>${escapeHtml(item)}</li>`).join("");
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

byId("refresh").addEventListener("click", () => load(state.session).catch((error) => showNotice(error.message)));
document.querySelectorAll(".view-tab").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.view).catch((error) => showNotice(error.message)));
});
document.querySelectorAll(".board-filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".board-filter").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    state.boardPosition = button.dataset.boardPosition;
    loadBoardView().catch((error) => showNotice(error.message));
  });
});
byId("board-available-only").addEventListener("change", () => loadBoardView().catch((error) => showNotice(error.message)));
byId("log-team").addEventListener("change", () => loadDraftLogView().catch((error) => showNotice(error.message)));
byId("log-position").addEventListener("change", () => loadDraftLogView().catch((error) => showNotice(error.message)));
document.addEventListener("click", (event) => {
  const player = event.target.closest("[data-player-id]");
  if (player) openPlayerDetail(player.dataset.playerId).catch((error) => showNotice(error.message));
});
byId("player-detail-close").addEventListener("click", () => byId("player-detail-dialog").close());
byId("player-detail-draft").addEventListener("click", () => {
  const player = state.detailPlayer;
  if (!player?.available) return;
  byId("player-detail-dialog").close();
  byId("command-input").value = `draft ${player.player}`;
  byId("command-form").requestSubmit();
});
byId("session-switcher").addEventListener("click", () => {
  showSessionNotice("");
  openSessionManager(false);
});
byId("session-dialog-close").addEventListener("click", () => byId("session-dialog").close());
byId("session-dialog").addEventListener("cancel", (event) => {
  if (state.sessions.length === 0) event.preventDefault();
});
byId("session-list").addEventListener("click", (event) => {
  const deleteButton = event.target.closest("[data-delete-session]");
  if (deleteButton) {
    const session = state.sessions.find((item) => item.name === deleteButton.dataset.deleteSession);
    if (!session) return;
    state.pendingDelete = { session, requestId: requestId() };
    byId("delete-session-name").textContent = session.name;
    byId("delete-session-text").textContent = `Delete ${session.name} at pick ${session.current_pick} with ${session.selections} recorded selections?`;
    byId("session-dialog").close();
    byId("delete-session-dialog").returnValue = "";
    byId("delete-session-dialog").showModal();
    return;
  }
  const option = event.target.closest("[data-session]");
  if (!option) return;
  loadSession(option.dataset.session).catch((error) => showSessionNotice(error.message));
});
byId("delete-session-dialog").addEventListener("close", async () => {
  const pending = state.pendingDelete;
  if (!pending) return;
  if (byId("delete-session-dialog").returnValue !== "confirm") {
    state.pendingDelete = null;
    openSessionManager(false);
    return;
  }
  try {
    const result = await api(`/api/v1/sessions/${encodeURIComponent(pending.session.name)}`, {
      method: "DELETE",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ request_id: pending.requestId }),
    });
    const deletedCurrent = state.session === pending.session.name;
    if (deletedCurrent) {
      state.session = null;
      forgetSession(pending.session.name);
      const url = new URL(window.location.href);
      url.searchParams.delete("session");
      history.replaceState(null, "", url);
    }
    state.pendingDelete = null;
    await load(deletedCurrent ? null : state.session);
    const message = `Deleted ${result.name}. Recovery copy saved in sessions/.trash.`;
    if (state.sessions.length === 0) showSessionNotice(message, true);
    else showNotice(message, true);
  } catch (error) {
    state.pendingDelete = null;
    openSessionManager(false);
    showSessionNotice(error.message);
  }
});
byId("new-league-size").addEventListener("input", () => {
  state.createRequestId = null;
  updateSessionCapacity();
});
["new-session-name", "new-rounds", "new-user-team"].forEach((id) => {
  byId(id).addEventListener("input", () => { state.createRequestId = null; });
});
byId("new-session-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const create = byId("create-session");
  const name = sessionSlug(byId("new-session-name").value);
  if (!name) {
    showSessionNotice("Enter a session name using letters or numbers.");
    return;
  }
  byId("new-session-name").value = name;
  state.createRequestId = state.createRequestId || requestId();
  create.disabled = true;
  showSessionNotice("Creating draft…");
  try {
    await api("/api/v1/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        league_size: Number(byId("new-league-size").value),
        rounds: Number(byId("new-rounds").value),
        user_team: Number(byId("new-user-team").value),
        request_id: state.createRequestId,
      }),
    });
    state.createRequestId = null;
    byId("new-session-form").reset();
    await load(name);
    showNotice(`Created and opened ${name}.`, true);
  } catch (error) {
    showSessionNotice(error.message);
  } finally {
    create.disabled = state.board?.health?.status !== "ready";
  }
});
byId("assistant-cancel").addEventListener("click", () => state.askController?.abort());
document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    byId("command-input").value = button.textContent.trim();
    byId("command-form").requestSubmit();
  });
});
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
      await askAssistant(text);
      return;
    }
    state.pendingPick = { ...interpretation, requestId: requestId() };
    byId("confirmation-player").textContent = interpretation.player.player;
    byId("confirmation-text").textContent = interpretation.confirmation.text;
    byId("confirmation-dialog").returnValue = "";
    byId("confirmation-dialog").showModal();
  } catch (error) {
    showNotice(error.name === "AbortError" ? "Question cancelled." : error.message);
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
