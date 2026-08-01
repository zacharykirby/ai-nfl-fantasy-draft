const state = {
  cockpit: null,
  position: "ALL",
  session: null,
  pendingPick: null,
  preparingPick: false,
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
  searchTimer: null,
  searchSequence: 0,
  serverOnline: false,
  copilotController: null,
  copilotSequence: 0,
  copilotKey: null,
  copilotResult: null,
  copilotOptionPlayers: {},
  assistantMode: "chill",
};

const byId = (id) => document.getElementById(id);

function formatScoring(value) {
  const scoring = String(value || "unknown").toLowerCase();
  if (scoring === "half_ppr") return "Half-PPR";
  if (scoring === "ppr") return "PPR";
  if (scoring === "standard") return "Standard";
  return scoring.replaceAll("_", " ");
}

function formatBoardDate(value) {
  if (!value) return "unknown date";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "unknown date";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

async function api(path, options = {}) {
  let response;
  try {
    response = await fetch(path, {
      ...options,
      headers: { Accept: "application/json", ...(options.headers || {}) },
    });
  } catch (error) {
    if (error.name !== "AbortError") {
      state.serverOnline = false;
      updateConnectivityIndicator();
      throw new Error("Server unreachable. The last confirmed draft state is still shown. Reconnect, then Refresh before recording another pick.");
    }
    throw error;
  }
  state.serverOnline = true;
  updateConnectivityIndicator();
  const payload = await response.json();
  if (!response.ok) throw new Error(payload?.error?.message || `Request failed (${response.status})`);
  return payload;
}

function playerRow(player) {
  return `<div class="player-row">
    <div>
      <div class="player-name">${escapeHtml(player.player)}</div>
      <div class="player-detail">${escapeHtml(player.position)} · ${escapeHtml(player.team || "FA")} · Bye ${player.bye_week ?? "—"} · Tier ${player.tier ?? "—"}</div>
    </div>
    <div class="rank-badge">${escapeHtml(player.position)}${player.position_rank ?? "—"}</div>
  </div>`;
}

function compactRow(left, right = "") {
  return `<div class="compact-row"><span>${escapeHtml(left)}</span><span class="player-detail">${escapeHtml(right)}</span></div>`;
}

function actionablePlayerRow(player, label = "Draft") {
  return `<div class="player-action">
    ${playerRow(player)}
    <button class="quick-draft" type="button" data-draft-player="${escapeHtml(player.player)}" aria-label="Draft ${escapeHtml(player.player)}">${label}</button>
  </div>`;
}

function setList(element, html, emptyText) {
  element.innerHTML = html || emptyText;
  element.classList.toggle("empty-state", !html);
}

function render(cockpit) {
  state.cockpit = cockpit;
  const session = cockpit.session;
  byId("session-name").textContent = session.name;
  const roundCount = Number(cockpit.league.rounds);
  const boardDate = formatBoardDate(state.board?.metadata?.generated_at || cockpit.health?.board_generated_at);
  const sourceStatus = state.board?.health?.source?.status || "snapshot";
  byId("league-context").textContent = `${formatScoring(cockpit.league.scoring)} · ${cockpit.league.league_size} teams · ${roundCount} round${roundCount === 1 ? "" : "s"} · Board ${boardDate} · source ${sourceStatus}`;
  byId("round").textContent = session.round;
  byId("current-pick").textContent = session.current_pick;
  byId("current-team").textContent = session.current_team == null
    ? "Done"
    : session.current_team === session.user_team ? "You" : `T${session.current_team}`;
  byId("your-turn").textContent = session.picks_until_user === 0 ? "Now" : session.picks_until_user ?? "Done";
  byId("available-count").textContent = `${session.available} total`;
  const draftComplete = session.status === "complete";
  byId("completion-card").hidden = !draftComplete;

  const recommendation = cockpit.recommendation;
  const primary = recommendation?.primary;
  byId("primary-player").textContent = primary?.player || "Draft complete";
  byId("primary-meta").textContent = primary
    ? `${primary.position}${primary.position_rank} · ${primary.team || "FA"} · Bye ${primary.bye_week ?? "—"} · Tier ${primary.tier} · ${Number(primary.vorp || 0).toFixed(1)} VORP`
    : "No active recommendation";
  byId("confidence").textContent = recommendation ? `${Math.round(recommendation.confidence * 100)}%` : "—";
  byId("mode").textContent = recommendation?.mode || "complete";
  byId("primary-reasons").innerHTML = (primary?.reasons || []).slice(0, 3)
    .map((reason) => `<li>${escapeHtml(reason)}</li>`).join("");
  byId("draft-primary").disabled = !primary;
  byId("draft-primary").dataset.draftPlayer = primary?.player || "";

  setList(
    byId("alternatives"),
    (recommendation?.alternatives || []).slice(0, 3).map((player) => actionablePlayerRow(player)).join(""),
    "No alternatives available",
  );
  renderAvailable();
  document.querySelectorAll("[data-draft-player]").forEach((button) => {
    button.disabled = draftComplete;
  });
  byId("player-search").disabled = draftComplete;
  if (draftComplete) {
    state.searchSequence += 1;
    byId("player-search").value = "";
    setList(byId("player-search-results"), "", "Draft complete · player selection is closed");
  }
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
  const run = cockpit.position_run || {};
  setList(
    byId("position-run"),
    run.active
      ? (run.positions || []).map((position) => compactRow(`${position} run`, `${run.counts?.[position] || 0} of last ${run.window}`)).join("")
      : "",
    "No active position run",
  );
  setList(
    byId("recent-picks"),
    cockpit.recent_picks.slice().reverse().map((pick) => compactRow(`${pick.overall_pick}. ${pick.player}`, `${pick.position} · Team ${pick.team}`)).join(""),
    "No selections yet",
  );
  renderHealth(cockpit.health);
  byId("undo-last").disabled = cockpit.recent_picks.length === 0;
  byId("catch-up").disabled = draftComplete;
  applyAssistantMode();
  syncCopilotForCockpit(cockpit);
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

function copilotKey(cockpit = state.cockpit) {
  if (!cockpit?.session || !state.session) return null;
  return `${state.session}:${cockpit.session.current_pick}:${cockpit.session.revision}`;
}

function applyAssistantMode() {
  const full = state.assistantMode === "full";
  byId("full-assistant-panel").hidden = !full;
  byId("assistant-mode-copy").textContent = full
    ? "Full assistant · deterministic lean stays visible"
    : "Chill · silent until asked";
}

function syncCopilotForCockpit(cockpit) {
  const key = copilotKey(cockpit);
  if (state.copilotKey && state.copilotKey !== key) {
    state.copilotController?.abort();
    state.copilotSequence += 1;
    state.copilotKey = null;
    state.copilotResult = null;
    state.copilotOptionPlayers = {};
    if (!byId("oh-god-card").hidden) {
      byId("oh-god-card").classList.add("stale");
      byId("oh-god-headline").textContent = "THE DRAFT MOVED.";
      byId("oh-god-explanation").textContent = "Tap OH GOD again for the current snapshot.";
      byId("oh-god-options").innerHTML = "";
    }
  }
  byId("oh-god").disabled = cockpit.session.status !== "active" || !cockpit.recommendation || Boolean(state.copilotController);
}

function setCopilotLoading(loading) {
  const button = byId("oh-god");
  button.disabled = loading || !state.cockpit?.recommendation;
  button.querySelector("span").textContent = loading ? "HOLD ON…" : "OH GOD";
  button.querySelector("small").textContent = loading ? "Reading this snapshot" : "Explain this draft snapshot";
}

function cockpitPlayer(playerId) {
  const pool = [
    state.cockpit?.recommendation?.primary,
    ...(state.cockpit?.recommendation?.alternatives || []),
    ...(state.cockpit?.best_available || []),
    ...Object.values(state.cockpit?.top_available_by_position || {}).flat(),
  ];
  return pool.find((player) => player?.player_id === playerId) || null;
}

async function resolveCopilotPlayers(result) {
  const options = [result.primary_option, result.safe_option, result.upside_option].filter(Boolean);
  const resolved = {};
  await Promise.all(options.map(async (option) => {
    const local = cockpitPlayer(option.player_id);
    if (local) {
      resolved[option.player_id] = local;
      return;
    }
    try {
      const detail = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/players/${encodeURIComponent(option.player_id)}`);
      resolved[option.player_id] = detail.player;
    } catch (_error) {
      resolved[option.player_id] = { player: option.player_id, position: "" };
    }
  }));
  return resolved;
}

function renderCopilot(payload) {
  const result = payload.result;
  const card = byId("oh-god-card");
  card.hidden = false;
  card.classList.toggle("stale", Boolean(payload.freshness.stale));
  card.dataset.urgency = result.urgency;
  byId("oh-god-headline").textContent = result.headline;
  byId("oh-god-urgency").textContent = payload.freshness.stale ? "STALE" : result.urgency.toUpperCase();
  byId("oh-god-explanation").textContent = payload.freshness.stale
    ? "The draft changed while this was being prepared. Tap OH GOD again."
    : result.explanation;
  const optionTypes = [
    ["primary_option", "Model/data lean"],
    ["safe_option", "Safer build"],
    ["upside_option", "Upside swing"],
  ];
  byId("oh-god-options").innerHTML = optionTypes.map(([field, heading]) => {
    const option = result[field];
    if (!option) return "";
    const player = state.copilotOptionPlayers[option.player_id] || {};
    const meta = [player.position, player.team].filter(Boolean).join(" · ");
    return `<button class="copilot-option" type="button" data-player-id="${escapeHtml(option.player_id)}">
      <span>${heading}</span><strong>${escapeHtml(player.player || option.player_id)}</strong>
      ${meta ? `<small>${escapeHtml(meta)}</small>` : ""}<p>${escapeHtml(option.reason)}</p>
    </button>`;
  }).join("");
  byId("oh-god-can-wait").textContent = `Can wait: ${result.can_wait}`;
  byId("oh-god-wait-reason").textContent = result.can_wait_reason;
  byId("oh-god-caveats").innerHTML = result.caveats.map((item) => `<li>${escapeHtml(item)}</li>`).join("");
  byId("oh-god-follow-up-answer").hidden = true;
  byId("oh-god-follow-ups").hidden = Boolean(payload.freshness.stale);
}

async function requestOhGod() {
  if (!state.session || !state.cockpit?.recommendation || state.copilotController) return;
  const requestedKey = copilotKey();
  const requestedPick = state.cockpit.session.current_pick;
  const requestedRevision = state.cockpit.session.revision;
  const sequence = ++state.copilotSequence;
  const controller = new AbortController();
  state.copilotController = controller;
  state.copilotKey = requestedKey;
  setCopilotLoading(true);
  try {
    const payload = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/assistant/oh-god`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ generated_for_pick: requestedPick, draft_revision: requestedRevision }),
      signal: controller.signal,
    });
    if (sequence !== state.copilotSequence || requestedKey !== copilotKey()) return;
    state.copilotResult = payload;
    state.copilotOptionPlayers = await resolveCopilotPlayers(payload.result);
    if (sequence !== state.copilotSequence) return;
    renderCopilot(payload);
  } catch (error) {
    if (error.name === "AbortError" || sequence !== state.copilotSequence) return;
    showNotice(`OH GOD is unavailable: ${error.message}`);
  } finally {
    if (state.copilotController === controller) state.copilotController = null;
    setCopilotLoading(false);
  }
}

async function requestCopilotFollowUp(intent) {
  if (!state.copilotResult || state.copilotResult.freshness.stale) return;
  const answer = byId("oh-god-follow-up-answer");
  answer.hidden = false;
  answer.textContent = "Checking this snapshot…";
  try {
    const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/assistant/oh-god/follow-up`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ intent, draft_revision: state.copilotResult.result.draft_revision }),
    });
    answer.textContent = result.answer;
    if (result.freshness.stale) syncCopilotForCockpit({ ...state.cockpit, session: { ...state.cockpit.session, revision: result.freshness.current_revision } });
  } catch (error) {
    answer.textContent = error.message;
  }
}

function renderAvailable() {
  if (!state.cockpit) return;
  const players = state.position === "ALL"
    ? state.cockpit.best_available
    : state.cockpit.top_available_by_position[state.position] || [];
  setList(
    byId("best-available"),
    players.map((player) => actionablePlayerRow(player)).join(""),
    "No players available",
  );
  byId("best-available-title").textContent = state.position === "ALL"
    ? "Best available"
    : `Best available · ${state.position}`;
  document.querySelectorAll(".filter").forEach((button) => {
    const selected = button.dataset.position === state.position;
    button.classList.toggle("active", selected);
    button.setAttribute("aria-pressed", String(selected));
  });
}

function setHealth(id, text, healthy = true) {
  const element = byId(id);
  element.textContent = text;
  element.classList.toggle("unhealthy", !healthy);
}

function renderHealth(health) {
  const runtimeBoard = state.board?.health;
  if (runtimeBoard) {
    setHealth("health-board", boardReadinessLabel(), runtimeBoard.can_create_session === true);
  } else {
    setHealth("health-board", health.board === "ready_snapshot" ? "Snapshot ready" : health.board, false);
  }
  setHealth("health-model", health.model === "configured" ? "Configured" : "Offline", true);
  setHealth("health-autosave", health.autosave === "ok" ? "Saved" : "Missing", health.autosave === "ok");
  updateConnectivityIndicator();
}

function updateConnectivityIndicator() {
  const element = byId("health-connectivity");
  if (!element) return;
  const browserOnline = navigator.onLine !== false;
  const connected = browserOnline && state.serverOnline;
  setHealth("health-connectivity", connected ? "Connected" : browserOnline ? "Server lost" : "Offline", connected);
}

async function beginPickConfirmation(playerName) {
  if (!playerName || !state.session || state.preparingPick || state.pendingPick) return;
  state.preparingPick = true;
  try {
    showNotice("Checking current draft state…");
    const interpretation = await interpretCommand(`draft ${playerName}`);
    if (interpretation.intent !== "record_pick") {
      throw new Error("That player could not be prepared for drafting.");
    }
    state.pendingPick = { ...interpretation, requestId: requestId() };
    byId("confirmation-player").textContent = interpretation.player.player;
    byId("confirmation-text").textContent = interpretation.confirmation.text;
    byId("confirmation-dialog").returnValue = "";
    byId("confirmation-dialog").showModal();
    showNotice("");
  } finally {
    state.preparingPick = false;
  }
}

async function searchPlayers(query, sequence = ++state.searchSequence) {
  const results = byId("player-search-results");
  if (query.length < 2) {
    setList(results, "", "Type at least 2 characters");
    return;
  }
  results.textContent = "Searching…";
  results.classList.add("empty-state");
  const payload = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/players/search?q=${encodeURIComponent(query)}&limit=8`);
  if (sequence !== state.searchSequence) return;
  setList(
    results,
    payload.players.map((player) => actionablePlayerRow(player)).join(""),
    "No available players match",
  );
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
  byId("full-board").classList.add("view-loading");
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
  byId("full-board").classList.remove("view-loading");
  byId("full-board").innerHTML = html || `<div class="card empty-state">No players match this board filter.</div>`;
}

async function loadRosterView() {
  const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/roster`);
  byId("roster-title").textContent = `Team ${result.team} · ${result.players.length} selections`;
  const positionCards = ["QB", "RB", "WR", "TE"].map((position) => {
    const need = result.needs[position];
    return `<div class="need-card ${need.open_base_slots ? "open" : ""}"><strong>${position}</strong><span>${need.rostered}/${need.base_starters} · ${need.open_base_slots} open</span></div>`;
  });
  const flexSlots = Number(state.cockpit?.league?.starters?.FLEX || 0);
  if (flexSlots) {
    const eligible = ["RB", "WR", "TE"];
    const extraEligible = eligible.reduce((total, position) => {
      const need = result.needs[position];
      return total + Math.max(0, Number(need.rostered) - Number(need.base_starters));
    }, 0);
    const filledFlex = Math.min(flexSlots, extraEligible);
    const openFlex = flexSlots - filledFlex;
    positionCards.push(`<div class="need-card ${openFlex ? "open" : ""}"><strong>FLEX</strong><span>${filledFlex}/${flexSlots} · ${openFlex} open</span></div>`);
  }
  byId("roster-needs").innerHTML = positionCards.join("");
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
  byId("player-detail-draft").hidden = !player.available || state.cockpit?.session?.status === "complete";
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
  state.searchSequence += 1;
  byId("player-search").value = "";
  setList(byId("player-search-results"), "", "Type at least 2 characters");
  const cockpit = await api(`/api/v1/sessions/${encodeURIComponent(name)}/cockpit`);
  state.session = name;
  state.copilotController?.abort();
  state.copilotSequence += 1;
  state.copilotController = null;
  state.copilotKey = null;
  state.copilotResult = null;
  state.copilotOptionPlayers = {};
  byId("oh-god-card").hidden = true;
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

function boardCanCreateSession() {
  return state.board?.health?.can_create_session === true;
}

function boardReadinessLabel() {
  const health = state.board?.health;
  if (!health) return "Checking board";
  if (health.can_create_session) return "Board ready";
  const blocked = [
    health.snapshot?.status !== "ready" ? "snapshot" : "",
    health.source?.status !== "ready" ? "source" : "",
    health.freshness?.status !== "ready" ? "freshness" : "",
  ].filter(Boolean);
  return `Blocked: ${blocked.join("/") || "validation"}`;
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
  byId("new-session-format").textContent = `Scoring: ${formatScoring(state.board?.league?.scoring)} · ${Number(state.board?.league?.starters?.FLEX || 0)} FLEX · ${Number(state.board?.league?.bench_size || 0)} bench`;
  byId("create-session").disabled = !boardCanCreateSession() || maxRounds < 1;
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
  const ready = boardCanCreateSession();
  byId("session-board-status").textContent = boardReadinessLabel();
  byId("session-board-status").classList.toggle("unhealthy", !ready);
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
  if (state.askController) return;
  const controller = new AbortController();
  state.askController = controller;
  byId("assistant-cancel").hidden = false;
  byId("talk-shop-send").disabled = true;
  showNotice("Asking the draft assistant…");
  try {
    const result = await api(`/api/v1/sessions/${encodeURIComponent(state.session)}/assistant/ask`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, mode: "balanced" }),
      signal: controller.signal,
    });
    renderAssistant(question, result);
    byId("talk-shop-input").value = "";
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
    byId("talk-shop-send").disabled = false;
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
  const recommendedPlayer = [
    state.cockpit?.recommendation?.primary,
    ...(state.cockpit?.recommendation?.alternatives || []),
    ...(state.cockpit?.best_available || []),
    ...Object.values(state.cockpit?.top_available_by_position || {}).flat(),
  ].find((player) => player?.player === answer.recommendation);
  const recommendationBye = recommendedPlayer?.bye_week == null
    ? ""
    : ` · Bye ${recommendedPlayer.bye_week}`;
  byId("assistant-recommendation").textContent = stale
    ? `Previous recommendation: ${answer.recommendation || "none"} — ask again`
    : answer.recommendation ? `Recommendation: ${answer.recommendation}${recommendationBye}` : "No single-player recommendation";
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
      expected_pick: state.pendingPick.confirmation.overall_pick,
      mode: "balanced",
    }),
  });
  render(result.cockpit);
  byId("command-input").value = "";
  byId("player-search").value = "";
  state.searchSequence += 1;
  setList(byId("player-search-results"), "", "Type at least 2 characters");
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
document.querySelectorAll("[data-results-view]").forEach((button) => {
  button.addEventListener("click", () => showView(button.dataset.resultsView).catch((error) => showNotice(error.message)));
});
document.querySelectorAll(".board-filter").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".board-filter").forEach((item) => {
      const selected = item === button;
      item.classList.toggle("active", selected);
      item.setAttribute("aria-pressed", String(selected));
    });
    state.boardPosition = button.dataset.boardPosition;
    loadBoardView().catch((error) => showNotice(error.message));
  });
});
byId("board-available-only").addEventListener("change", () => loadBoardView().catch((error) => showNotice(error.message)));
byId("log-team").addEventListener("change", () => loadDraftLogView().catch((error) => showNotice(error.message)));
byId("log-position").addEventListener("change", () => loadDraftLogView().catch((error) => showNotice(error.message)));
document.addEventListener("click", (event) => {
  const draftButton = event.target.closest("[data-draft-player]");
  if (draftButton) {
    beginPickConfirmation(draftButton.dataset.draftPlayer)
      .catch((error) => showNotice(error.message));
    return;
  }
  const player = event.target.closest("[data-player-id]");
  if (player) openPlayerDetail(player.dataset.playerId).catch((error) => showNotice(error.message));
});
byId("player-detail-close").addEventListener("click", () => byId("player-detail-dialog").close());
byId("player-detail-draft").addEventListener("click", () => {
  const player = state.detailPlayer;
  if (!player?.available) return;
  byId("player-detail-dialog").close();
  beginPickConfirmation(player.player).catch((error) => showNotice(error.message));
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
    await showView("cockpit");
    showNotice(`Created and opened ${name}.`, true);
  } catch (error) {
    showSessionNotice(error.message);
  } finally {
    create.disabled = !boardCanCreateSession();
  }
});
byId("assistant-cancel").addEventListener("click", () => state.askController?.abort());
byId("oh-god").addEventListener("click", () => requestOhGod());
byId("assistant-mode").addEventListener("change", (event) => {
  state.assistantMode = event.target.value === "full" ? "full" : "chill";
  applyAssistantMode();
});
document.querySelectorAll("[data-copilot-follow-up]").forEach((button) => {
  button.addEventListener("click", () => requestCopilotFollowUp(button.dataset.copilotFollowUp));
});
document.querySelectorAll(".prompt-chip").forEach((button) => {
  button.addEventListener("click", () => {
    byId("talk-shop").open = true;
    byId("talk-shop-input").value = button.textContent.trim();
    byId("talk-shop-form").requestSubmit();
  });
});
byId("talk-shop-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = byId("talk-shop-input").value.trim();
  if (!question) return;
  try {
    await askAssistant(question);
  } catch (error) {
    showNotice(error.name === "AbortError" ? "Question cancelled." : error.message);
  }
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
    state.position = button.dataset.position;
    renderAvailable();
  });
});
byId("player-search").addEventListener("input", (event) => {
  clearTimeout(state.searchTimer);
  const query = event.target.value.trim();
  const sequence = ++state.searchSequence;
  state.searchTimer = setTimeout(() => {
    searchPlayers(query, sequence).catch((error) => showNotice(error.message));
  }, 150);
});
window.addEventListener("online", () => {
  updateConnectivityIndicator();
  load(state.session).catch((error) => showNotice(error.message));
});
window.addEventListener("offline", updateConnectivityIndicator);
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
      byId("talk-shop").open = true;
      byId("talk-shop-input").value = text;
      input.value = "";
      showNotice("That sounds like a question. It is ready in Talk shop—tap Ask when you want an answer.", true);
      byId("talk-shop-input").focus();
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
