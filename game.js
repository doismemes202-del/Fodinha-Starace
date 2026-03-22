/**
 * game.js – Cliente WebSocket do Fodinha Online
 *
 * Fluxo:
 *   1. Lobby → usuário escolhe nickname e sala → conecta via WebSocket
 *   2. Recebe mensagens do tipo "connected", "state", "chat", "error"
 *   3. Envia: start_game, make_bet, play_card, next_round, chat
 */

// ------------------------------------------------------------------ //
// Estado local
// ------------------------------------------------------------------ //
let ws = null;
let myPid = null;
let myNickname = "";
let roomId = "default";
let lastState = null;

// ------------------------------------------------------------------ //
// Elementos DOM
// ------------------------------------------------------------------ //
const screenLobby   = document.getElementById("screen-lobby");
const screenGame    = document.getElementById("screen-game");
const lobbyError    = document.getElementById("lobby-error");
const inputNick     = document.getElementById("input-nick");
const inputRoom     = document.getElementById("input-room");
const btnEnter      = document.getElementById("btn-enter");

const gameRoundInfo = document.getElementById("game-round-info");
const statusBanner  = document.getElementById("status-banner");
const playersList   = document.getElementById("players-list");
const viraDisplay   = document.getElementById("vira-display");
const manilhaDisplay= document.getElementById("manilha-display");
const tableArea     = document.getElementById("table-area");
const tableEmpty    = document.getElementById("table-empty");
const betArea       = document.getElementById("bet-area");
const betTitle      = document.getElementById("bet-title");
const betButtons    = document.getElementById("bet-buttons");
const betRestriction= document.getElementById("bet-restriction");
const myHand        = document.getElementById("my-hand");
const btnStart      = document.getElementById("btn-start");
const btnNextRound  = document.getElementById("btn-next-round");
const eventLog      = document.getElementById("event-log");
const chatInput     = document.getElementById("chat-input");
const btnChat       = document.getElementById("btn-chat");
const modalGameover = document.getElementById("modal-gameover");
const gameoverText  = document.getElementById("gameover-text");
const btnNewGame    = document.getElementById("btn-new-game");

// ------------------------------------------------------------------ //
// Lobby
// ------------------------------------------------------------------ //
btnEnter.addEventListener("click", joinRoom);
inputNick.addEventListener("keydown", e => { if (e.key === "Enter") joinRoom(); });

function joinRoom() {
  const nick = inputNick.value.trim();
  const room = inputRoom.value.trim() || "default";
  if (!nick) { lobbyError.textContent = "Digite um apelido!"; return; }
  lobbyError.textContent = "";
  myNickname = nick;
  roomId = room;
  connectWS(nick, room);
}

// ------------------------------------------------------------------ //
// WebSocket
// ------------------------------------------------------------------ //
function connectWS(nickname, room) {
  const proto = location.protocol === "https:" ? "wss" : "ws";
  const url = `${proto}://${location.host}/ws/${encodeURIComponent(room)}?nickname=${encodeURIComponent(nickname)}`;
  ws = new WebSocket(url);

  ws.onopen = () => {
    lobbyError.textContent = "";
  };

  ws.onmessage = evt => {
    let msg;
    try { msg = JSON.parse(evt.data); } catch { return; }
    handleServerMessage(msg);
  };

  ws.onclose = () => {
    setStatus("Desconectado. Recarregue a página.", "danger");
  };

  ws.onerror = () => {
    lobbyError.textContent = "Erro de conexão. Verifique o servidor.";
  };
}

function send(obj) {
  if (ws && ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify(obj));
  }
}

// ------------------------------------------------------------------ //
// Tratamento de mensagens do servidor
// ------------------------------------------------------------------ //
function handleServerMessage(msg) {
  if (msg.type === "connected") {
    myPid = msg.pid;
    // Troca de tela
    screenLobby.classList.add("hidden");
    screenGame.classList.remove("hidden");
    setStatus("Aguardando jogadores…");
  }

  else if (msg.type === "state") {
    lastState = msg.state;
    renderState(msg.state);
  }

  else if (msg.type === "chat") {
    appendLog(`💬 ${msg.nickname}: ${msg.text}`);
  }

  else if (msg.type === "error") {
    setStatus(`⚠️ ${msg.message}`, "warn");
  }
}

// ------------------------------------------------------------------ //
// Renderização do estado
// ------------------------------------------------------------------ //
function renderState(state) {
  const phase = state.phase;

  // Cabeçalho
  gameRoundInfo.textContent =
    `Rodada ${state.round_number || "—"} | ${state.n_cards || "—"} carta(s) | Fase: ${phaseLabel(phase)}`;

  // Vira
  if (state.vira) {
    if (state.vira.hidden) {
      viraDisplay.textContent = "🂠 (oculto)";
      manilhaDisplay.textContent = "?";
    } else {
      viraDisplay.textContent = state.vira.display || state.vira.short || "—";
      manilhaDisplay.textContent = state.manilha_value
        ? `${state.manilha_value} (manilha)`
        : "—";
    }
  } else {
    viraDisplay.textContent = "—";
    manilhaDisplay.textContent = "—";
  }

  // Jogadores
  renderPlayers(state);

  // Mesa
  renderTable(state);

  // Mão
  renderHand(state);

  // Botão iniciar
  btnStart.classList.toggle("hidden", phase !== "waiting");

  // Botão próxima rodada
  const showNext = phase === "round_end" && isMe(state.dealer_pid);
  btnNextRound.classList.toggle("hidden", !showNext);

  // Palpite
  const myTurnToBet = (phase === "betting" || phase === "final_duel")
    && state.current_bettor_pid === myPid;
  if (myTurnToBet) {
    renderBetUI(state);
  } else {
    betArea.classList.add("hidden");
  }

  // Status
  updateStatusBanner(state);

  // Log
  renderLog(state.event_log);

  // Game over
  if (phase === "game_over") {
    const lastLog = state.event_log[state.event_log.length - 1] || "Fim de jogo!";
    gameoverText.textContent = lastLog;
    modalGameover.classList.remove("hidden");
  } else {
    modalGameover.classList.add("hidden");
  }
}

// ------------------------------------------------------------------ //
// Jogadores
// ------------------------------------------------------------------ //
function renderPlayers(state) {
  playersList.innerHTML = "";
  for (const p of state.players) {
    const chip = document.createElement("div");
    chip.className = "player-chip";
    if (p.pid === myPid)                chip.classList.add("is-me");
    if (p.pid === state.dealer_pid)     chip.classList.add("is-dealer");
    if (!p.active)                      chip.classList.add("eliminated");

    const isActiveTurn = p.pid === state.current_bettor_pid
                      || p.pid === state.current_player_pid;
    if (isActiveTurn) chip.classList.add("is-active-turn");

    if (p.pid === state.dealer_pid) {
      const badge = document.createElement("span");
      badge.className = "dealer-badge";
      badge.textContent = "D";
      chip.appendChild(badge);
    }

    chip.innerHTML += `
      <span class="nick">${esc(p.nickname)}${p.pid === myPid ? " (você)" : ""}</span>
      <span class="lives">❤️ ${p.lives}</span>
      ${p.bet !== null ? `<span class="bet-info">📢 ${p.bet}</span>` : ""}
      ${p.tricks_won > 0 ? `<span class="bet-info" style="color:#adf">✔ ${p.tricks_won}</span>` : ""}
      ${!p.active ? `<span style="font-size:.7rem;color:#f88">💀</span>` : ""}
    `;
    playersList.appendChild(chip);
  }
}

// ------------------------------------------------------------------ //
// Mesa
// ------------------------------------------------------------------ //
function renderTable(state) {
  // Remover slots anteriores mas manter o "table-empty"
  Array.from(tableArea.children).forEach(c => {
    if (c !== tableEmpty) c.remove();
  });

  // Mostrar cartas jogadas na vaza atual
  const plays = state.players
    .filter(p => p.played_card)
    .map(p => ({ nickname: p.nickname, card: p.played_card }));

  if (plays.length === 0) {
    tableEmpty.style.display = "";
    return;
  }
  tableEmpty.style.display = "none";

  for (const { nickname, card } of plays) {
    const slot = document.createElement("div");
    slot.className = "played-card-slot";
    slot.innerHTML = `${buildCardHTML(card)}<span>${esc(nickname)}</span>`;
    tableArea.appendChild(slot);
  }
}

// ------------------------------------------------------------------ //
// Mão do jogador
// ------------------------------------------------------------------ //
function renderHand(state) {
  myHand.innerHTML = "";
  const me = state.players.find(p => p.pid === myPid);
  if (!me) return;

  const phase = state.phase;
  const canPlay = phase === "playing" && state.current_player_pid === myPid;

  for (const slot of me.hand) {
    const wrapper = document.createElement("div");
    if (slot.card) {
      wrapper.innerHTML = buildCardHTML(slot.card, canPlay, slot.index);
      if (canPlay) {
        const cardEl = wrapper.firstElementChild;
        cardEl.addEventListener("click", () => playCard(slot.index));
      }
    } else {
      // Carta oculta para este jogador
      wrapper.innerHTML = buildCardBack();
    }
    myHand.appendChild(wrapper);
  }
}

// ------------------------------------------------------------------ //
// UI de Palpite
// ------------------------------------------------------------------ //
function renderBetUI(state) {
  betArea.classList.remove("hidden");

  const me = state.players.find(p => p.pid === myPid);
  const isDealer = state.dealer_pid === myPid;
  const n = state.n_cards;
  const betsPlaced = state.players
    .filter(p => p.active && p.bet !== null)
    .map(p => p.bet);
  const sumSoFar = betsPlaced.reduce((a, b) => a + b, 0);

  betTitle.textContent = `Faça seu palpite (0–${n}):`;
  betButtons.innerHTML = "";
  betRestriction.textContent = "";

  for (let i = 0; i <= n; i++) {
    const btn = document.createElement("button");
    btn.className = "bet-btn";
    btn.textContent = i;

    // Checar restrições client-side (servidor valida de qualquer forma)
    let disabled = false;
    let reason = "";

    if (isDealer) {
      if (sumSoFar + i === n) {
        disabled = true;
        reason = `Proibido (soma ficaria ${n})`;
      }
      if (i >= 1 && betsPlaced.every(b => b === 0)) {
        disabled = true;
        reason = "Dealer não pode palpitar ≥1 se nenhum apostou ≥1";
      }
    } else {
      // Último a apostar antes do dealer
      const remainingPlayers = state.players.filter(p => p.active && p.bet === null).length;
      if (remainingPlayers === 1 && sumSoFar + i === n) {
        disabled = true;
        reason = `Proibido (soma ficaria ${n})`;
      }
    }

    btn.disabled = disabled;
    btn.title = reason;
    btn.addEventListener("click", () => {
      if (!disabled) makeBet(i);
    });
    betButtons.appendChild(btn);
  }

  if (isDealer) {
    betRestriction.textContent = `Dealer: a soma dos palpites não pode ser ${n}.`;
  }
}

// ------------------------------------------------------------------ //
// Construtores HTML de carta
// ------------------------------------------------------------------ //
function buildCardHTML(card, playable = false, index = null) {
  if (!card) return buildCardBack();

  const suitClass = card.is_joker ? "suit-J" : `suit-${card.suit}`;
  const suitSymbol = suitSymbols[card.suit] || "★";
  const val = card.is_joker ? "JK" : card.value;
  const classes = ["card", suitClass];
  if (playable) classes.push("playable");
  if (card.is_joker) classes.push("joker");

  const dataIdx = index !== null ? `data-index="${index}"` : "";

  return `
    <div class="${classes.join(" ")}" ${dataIdx}>
      <span class="val">${val}</span>
      <span class="suit-icon">${suitSymbol}</span>
    </div>
  `;
}

function buildCardBack() {
  return `<div class="card back"></div>`;
}

const suitSymbols = { O: "♦", E: "♠", C: "♥", P: "♣", J: "★" };

// ------------------------------------------------------------------ //
// Status Banner
// ------------------------------------------------------------------ //
function updateStatusBanner(state) {
  const phase = state.phase;

  if (phase === "waiting") {
    const n = state.players.filter(p => p.active).length;
    setStatus(`Sala: ${n} jogador(es). Aguarde o início…`);
    return;
  }

  if (phase === "betting" || phase === "final_duel") {
    if (state.current_bettor_pid === myPid) {
      setStatus("🎯 Sua vez de apostar!", "warn");
    } else {
      const bettor = findNickname(state, state.current_bettor_pid);
      setStatus(`Aguardando palpite de ${bettor}…`);
    }
    return;
  }

  if (phase === "playing") {
    if (state.current_player_pid === myPid) {
      setStatus("🃏 Sua vez de jogar!", "warn");
    } else {
      const whose = findNickname(state, state.current_player_pid);
      setStatus(`Aguardando jogada de ${whose}…`);
    }
    return;
  }

  if (phase === "round_end") {
    if (isMe(state.dealer_pid)) {
      setStatus("Rodada encerrada. Clique em Próxima Rodada.", "warn");
    } else {
      const dealer = findNickname(state, state.dealer_pid);
      setStatus(`Rodada encerrada. Aguardando ${dealer} avançar…`);
    }
    return;
  }

  if (phase === "game_over") {
    setStatus("🏆 Fim de jogo!", "warn");
    return;
  }
}

// ------------------------------------------------------------------ //
// Log de eventos
// ------------------------------------------------------------------ //
let loggedLines = new Set();

function renderLog(lines) {
  if (!lines) return;
  let changed = false;
  for (const line of lines) {
    if (!loggedLines.has(line)) {
      loggedLines.add(line);
      appendLog(line);
      changed = true;
    }
  }
  if (changed) eventLog.scrollTop = eventLog.scrollHeight;
}

function appendLog(text) {
  const p = document.createElement("p");
  p.textContent = text;
  eventLog.appendChild(p);
  eventLog.scrollTop = eventLog.scrollHeight;
}

// ------------------------------------------------------------------ //
// Ações do jogador
// ------------------------------------------------------------------ //
function makeBet(bet) {
  send({ type: "make_bet", bet });
}

function playCard(index) {
  send({ type: "play_card", card_index: index });
}

btnStart.addEventListener("click", () => send({ type: "start_game" }));

btnNextRound.addEventListener("click", () => send({ type: "next_round" }));

chatInput.addEventListener("keydown", e => {
  if (e.key === "Enter") sendChat();
});
btnChat.addEventListener("click", sendChat);

function sendChat() {
  const text = chatInput.value.trim();
  if (text) {
    send({ type: "chat", text });
    chatInput.value = "";
  }
}

btnNewGame.addEventListener("click", () => {
  location.reload();
});

// ------------------------------------------------------------------ //
// Utilitários
// ------------------------------------------------------------------ //
function setStatus(msg, cls = "") {
  statusBanner.textContent = msg;
  statusBanner.className = cls ? `${cls}` : "";
  // re-add base id styling (no class override)
  statusBanner.id = "status-banner";
}

function isMe(pid) { return pid === myPid; }

function findNickname(state, pid) {
  const p = state.players.find(pl => pl.pid === pid);
  return p ? p.nickname : pid;
}

function esc(str) {
  const d = document.createElement("div");
  d.textContent = String(str);
  return d.innerHTML;
}

function phaseLabel(phase) {
  const labels = {
    waiting:     "Aguardando",
    betting:     "Palpites",
    playing:     "Jogadas",
    round_end:   "Fim de Rodada",
    final_duel:  "Duelo Final",
    game_over:   "Fim de Jogo",
  };
  return labels[phase] || phase;
}
