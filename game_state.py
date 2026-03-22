"""
game_state.py - Máquina de estados principal da partida Fodinha.

Estados:
  WAITING       → Aguardando jogadores suficientes
  BETTING       → Fase de palpites
  PLAYING       → Fase de jogadas (vazas)
  ROUND_END     → Fim de rodada (mostra resultado antes de avançar)
  FINAL_DUEL    → Duelo final (2 jogadores)
  GAME_OVER     → Fim da partida
"""

from __future__ import annotations
import uuid
import logging
from enum import Enum
from typing import Optional
from .cards import Card, get_manilha_value, JOKER
from .player import Player, INITIAL_LIVES
from .rules import (
    cards_for_round, deal_cards, resolve_trick, validate_bet,
    ROUND_CARD_COUNTS
)

logger = logging.getLogger(__name__)

MAX_PLAYERS = 6
MIN_PLAYERS = 2


class Phase(str, Enum):
    WAITING = "waiting"
    BETTING = "betting"
    PLAYING = "playing"
    ROUND_END = "round_end"
    FINAL_DUEL = "final_duel"
    GAME_OVER  = "game_over"


class GameState:
    """Estado completo de uma sala/partida."""

    def __init__(self, room_id: str):
        self.room_id = room_id
        self.players: list[Player] = []         # ordenados por posição na mesa
        self.phase: Phase = Phase.WAITING

        # Rodada
        self.round_number: int = 0              # 1-indexed
        self.dealer_index: int = 0              # índice no array players
        self.n_cards: int = 0
        self.vira: Optional[Card] = None
        self.extra_viras: list[Card] = []
        self.vira_was_joker: bool = False
        self.manilha_value: str = ""

        # Vira oculto durante palpites (rodada 6 e Duelo Final)
        self.hide_vira_during_betting: bool = False

        # Palpites
        self.bet_order: list[str] = []          # lista de pids na ordem de apostas
        self.bet_index: int = 0                 # próximo a apostar

        # Jogadas
        self.trick_order: list[str] = []        # pids na ordem de jogada da vaza
        self.trick_index: int = 0
        self.current_trick_plays: list[tuple[Player, Card]] = []
        self.trick_starter_pid: str = ""        # pid de quem começa a vaza atual
        self.tricks_played: int = 0             # vazas já jogadas nesta rodada

        # Duelo final
        self.is_final_duel: bool = False

        # Log de eventos (últimas mensagens)
        self.event_log: list[str] = []

    # ------------------------------------------------------------------ #
    # Gerenciamento de jogadores
    # ------------------------------------------------------------------ #

    def add_player(self, pid: str, nickname: str) -> Optional[str]:
        """Adiciona jogador; retorna mensagem de erro ou None se ok."""
        if len(self.players) >= MAX_PLAYERS:
            return "Sala cheia."
        if any(p.pid == pid for p in self.players):
            return "Jogador já está na sala."
        if self.phase != Phase.WAITING:
            return "Partida em andamento."
        player = Player(pid=pid, nickname=nickname)
        self.players.append(player)
        self._log(f"{nickname} entrou na sala.")
        return None

    def remove_player(self, pid: str) -> None:
        player = self._get_player(pid)
        if player:
            player.connected = False
            self._log(f"{player.nickname} saiu.")

    def reconnect_player(self, pid: str) -> bool:
        player = self._get_player(pid)
        if player:
            player.connected = True
            return True
        return False

    # ------------------------------------------------------------------ #
    # Início de partida / rodada
    # ------------------------------------------------------------------ #

    def can_start(self) -> bool:
        return len(self.active_players) >= MIN_PLAYERS and self.phase == Phase.WAITING

    @property
    def active_players(self) -> list[Player]:
        return [p for p in self.players if p.active]

    def start_game(self) -> Optional[str]:
        if not self.can_start():
            return "Não é possível iniciar: jogadores insuficientes ou partida já em andamento."
        self.round_number = 0
        self.dealer_index = 0
        self._start_round()
        return None

    def _start_round(self) -> None:
        """Inicia uma nova rodada."""
        self.round_number += 1
        active = self.active_players

        # Verificar Duelo Final
        if len(active) == 2 and not self.is_final_duel:
            self.is_final_duel = True
            self._log("⚔️ DUELO FINAL! Apenas 2 jogadores restam.")

        # No duelo final, usa 6 cartas com vira oculto
        if self.is_final_duel:
            self.n_cards = 6
            self.hide_vira_during_betting = True
            self.phase = Phase.FINAL_DUEL
        else:
            self.n_cards = cards_for_round(self.round_number)
            # Rodada 6 oculta o vira durante palpites
            idx = (self.round_number - 1) % len(ROUND_CARD_COUNTS)
            self.hide_vira_during_betting = (idx + 1 == 6)
            self.phase = Phase.BETTING

        # Distribuir cartas e determinar vira
        self.vira, self.extra_viras, self.vira_was_joker = deal_cards(active, self.round_number if not self.is_final_duel else 6)
        self.manilha_value = get_manilha_value(self.vira)

        # Atualizar n_cards com o real (pode ter sido reduzido por falta de cartas)
        self.n_cards = len(active[0].hand) if active else self.n_cards

        # Ordem de palpites: começa à direita do dealer (próximo no sentido horário)
        self.bet_order = self._order_from_right_of_dealer(active)
        self.bet_index = 0

        # Início da primeira vaza: mesmo da bet_order (à direita do dealer)
        self.trick_starter_pid = self.bet_order[0]
        self.trick_order = list(self.bet_order)
        self.trick_index = 0

        self.current_trick_plays = []
        self.tricks_played = 0

        self._log(f"--- Rodada {self.round_number} | {self.n_cards} carta(s) ---")
        if self.vira_was_joker:
            self._log("🃏 Vira foi JOKER! ZAP é invencível esta rodada.")
        self._log(f"Vira: {self.vira.display_name} | Manilha: {self.manilha_value}")

    def _order_from_right_of_dealer(self, active: list[Player]) -> list[str]:
        """Retorna pids na ordem começando à direita do dealer (horário)."""
        n = len(active)
        # dealer_index referencia ao array self.players; precisamos mapear para active
        dealer_pid = self.players[self.dealer_index % len(self.players)].pid
        dealer_pos_in_active = next(
            (i for i, p in enumerate(active) if p.pid == dealer_pid), 0
        )
        start = (dealer_pos_in_active + 1) % n
        return [active[(start + i) % n].pid for i in range(n)]

    # ------------------------------------------------------------------ #
    # Apostas
    # ------------------------------------------------------------------ #

    def current_bettor_pid(self) -> Optional[str]:
        if self.bet_index < len(self.bet_order):
            return self.bet_order[self.bet_index]
        return None

    def make_bet(self, pid: str, bet: int) -> Optional[str]:
        """Registra palpite. Retorna mensagem de erro ou None."""
        if self.phase not in (Phase.BETTING, Phase.FINAL_DUEL):
            return "Não é fase de palpites."
        if pid != self.current_bettor_pid():
            return "Não é sua vez de apostar."

        active = self.active_players
        bets_so_far = [p.bet for p in active if p.bet is not None]
        is_dealer = (pid == self._dealer_pid())

        err = validate_bet(bet, self.n_cards, bets_so_far, is_dealer, len(active))
        if err:
            return err

        player = self._get_player(pid)
        player.bet = bet
        self.bet_index += 1
        self._log(f"{player.nickname} apostou {bet} vaza(s).")

        # Se todos apostaram, vai para fase de jogadas
        if self.bet_index >= len(self.bet_order):
            self.phase = Phase.PLAYING
            self._setup_trick()
            self._log("Fase de apostas concluída. Iniciando vazas.")

        return None

    def _dealer_pid(self) -> str:
        return self.players[self.dealer_index % len(self.players)].pid

    # ------------------------------------------------------------------ #
    # Jogadas / Vazas
    # ------------------------------------------------------------------ #

    def _setup_trick(self) -> None:
        """Prepara a ordem de jogada da vaza atual."""
        active = self.active_players
        n = len(active)
        starter_pos = next(
            (i for i, p in enumerate(active) if p.pid == self.trick_starter_pid), 0
        )
        self.trick_order = [active[(starter_pos + i) % n].pid for i in range(n)]
        self.trick_index = 0
        self.current_trick_plays = []

    def current_player_pid(self) -> Optional[str]:
        if self.phase == Phase.PLAYING and self.trick_index < len(self.trick_order):
            return self.trick_order[self.trick_index]
        return None

    def play_card(self, pid: str, card_index: int) -> Optional[str]:
        """Jogador pid joga a carta no índice card_index da mão.
        Retorna erro ou None.
        """
        if self.phase != Phase.PLAYING:
            return "Não é fase de jogadas."
        if pid != self.current_player_pid():
            return "Não é sua vez de jogar."

        player = self._get_player(pid)
        if card_index < 0 or card_index >= len(player.hand):
            return "Índice de carta inválido."

        card = player.hand.pop(card_index)
        # Reindexar visibilidade
        new_vis = {}
        for k, v in player.card_visibility.items():
            if k < card_index:
                new_vis[k] = v
            elif k > card_index:
                new_vis[k - 1] = v
        player.card_visibility = new_vis

        player.played_card = card
        self.current_trick_plays.append((player, card))
        self.trick_index += 1
        self._log(f"{player.nickname} jogou {card.display_name}.")

        # Todos jogaram na vaza?
        if self.trick_index >= len(self.trick_order):
            self._resolve_trick()

        return None

    def _resolve_trick(self) -> None:
        """Resolve a vaza atual e avança o estado."""
        winner = resolve_trick(
            self.current_trick_plays,
            self.manilha_value,
            self.vira_was_joker,
        )
        winner.tricks_won += 1
        self.tricks_played += 1
        self._log(f"✔ {winner.nickname} venceu a vaza!")

        # Reset played_card
        for p, _ in self.current_trick_plays:
            p.played_card = None

        # Quem ganhou "torna" (começa a próxima vaza)
        self.trick_starter_pid = winner.pid

        # Todas as vazas da rodada foram jogadas?
        if self.tricks_played >= self.n_cards:
            self._end_round()
        else:
            self._setup_trick()

    def _end_round(self) -> None:
        """Finaliza a rodada, calcula vidas e verifica eliminações."""
        active = self.active_players
        results = []
        for player in active:
            x = player.bet if player.bet is not None else 0
            y = player.tricks_won
            lost = abs(x - y)
            if lost > 0:
                player.lose_lives(lost)
                results.append(f"{player.nickname}: apostou {x}, fez {y} → -{lost} vida(s) ({player.lives} restantes)")
            else:
                results.append(f"{player.nickname}: apostou {x}, fez {y} → acertou! ✅ ({player.lives} vidas)")

        self._log("=== Resultado da Rodada ===")
        for r in results:
            self._log(r)

        # Eliminar jogadores com 0 vidas
        for p in self.players:
            if p.active and p.lives == 0:
                p.active = False
                self._log(f"💀 {p.nickname} foi eliminado!")

        # Avançar dealer para a direita (horário)
        self._advance_dealer()

        self.phase = Phase.ROUND_END

        # Verificar fim de jogo
        still_active = self.active_players
        if len(still_active) == 0:
            self.phase = Phase.GAME_OVER
            self._log("Todos eliminados. Empate!")
        elif len(still_active) == 1:
            self.phase = Phase.GAME_OVER
            self._log(f"🏆 {still_active[0].nickname} venceu o jogo!")
        elif self.is_final_duel:
            # Já estamos no duelo final — verificar se acabou
            self.phase = Phase.GAME_OVER
            top = max(still_active, key=lambda p: p.lives)
            tied = [p for p in still_active if p.lives == top.lives]
            if len(tied) == 1:
                self._log(f"🏆 {top.nickname} venceu o Duelo Final!")
            else:
                self._log("Duelo Final empatado! Repetindo duelo...")
                self.phase = Phase.ROUND_END  # vai repetir o duelo

    def _advance_dealer(self) -> None:
        """Move o dealer para o próximo jogador ativo."""
        n = len(self.players)
        for _ in range(n):
            self.dealer_index = (self.dealer_index + 1) % n
            if self.players[self.dealer_index].active:
                break

    def next_round(self) -> None:
        """Chamado após ROUND_END para iniciar a próxima rodada."""
        if self.phase == Phase.ROUND_END:
            self._start_round()

    # ------------------------------------------------------------------ #
    # Serialização do estado
    # ------------------------------------------------------------------ #

    def to_dict(self, viewer_pid: Optional[str] = None) -> dict:
        """Serializa o estado visível para viewer_pid."""
        reveal = self.phase in (Phase.ROUND_END, Phase.GAME_OVER)

        # Vira: oculto durante palpites na rodada 6 / Duelo Final
        show_vira = not (
            self.hide_vira_during_betting
            and self.phase in (Phase.BETTING, Phase.FINAL_DUEL)
        )

        vira_data = None
        if self.vira and show_vira:
            vira_data = self.vira.to_dict()
        elif self.vira and not show_vira:
            vira_data = {"hidden": True}

        return {
            "room_id": self.room_id,
            "phase": self.phase.value,
            "round_number": self.round_number,
            "n_cards": self.n_cards,
            "vira": vira_data,
            "extra_viras": [v.to_dict() for v in self.extra_viras],
            "vira_was_joker": self.vira_was_joker,
            "manilha_value": self.manilha_value if show_vira else None,
            "dealer_pid": self._dealer_pid() if self.players else None,
            "current_bettor_pid": self.current_bettor_pid(),
            "current_player_pid": self.current_player_pid(),
            "trick_starter_pid": self.trick_starter_pid,
            "tricks_played": self.tricks_played,
            "is_final_duel": self.is_final_duel,
            "players": [p.to_dict(viewer_pid=viewer_pid, reveal_hand=reveal) for p in self.players],
            "event_log": self.event_log[-20:],  # últimos 20 eventos
        }

    # ------------------------------------------------------------------ #
    # Utilitários
    # ------------------------------------------------------------------ #

    def _get_player(self, pid: str) -> Optional[Player]:
        return next((p for p in self.players if p.pid == pid), None)

    def _log(self, msg: str) -> None:
        self.event_log.append(msg)
        logger.info("[%s] %s", self.room_id, msg)
