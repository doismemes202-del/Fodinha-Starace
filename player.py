"""
player.py - Modelo de jogador para o jogo Fodinha.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from .cards import Card

INITIAL_LIVES = 5


@dataclass
class Player:
    """Representa um jogador na partida."""

    pid: str          # ID único (gerado no servidor)
    nickname: str
    lives: int = INITIAL_LIVES

    # Estado da rodada atual
    hand: list[Card] = field(default_factory=list)
    bet: Optional[int] = None        # Palpite da rodada
    tricks_won: int = 0              # Vazas ganhas na rodada
    played_card: Optional[Card] = None

    # Visibilidade das cartas (rodada especial - 3 cartas)
    # Mapeamento: índice da carta → visibilidade
    # "self" = apenas o próprio vê; "others" = outros veem; "none" = ninguém vê
    card_visibility: dict[int, str] = field(default_factory=dict)

    # Se o jogador está ativo (não eliminado)
    active: bool = True

    # Se ainda está conectado
    connected: bool = True

    def reset_round(self) -> None:
        """Reseta estado da rodada."""
        self.hand = []
        self.bet = None
        self.tricks_won = 0
        self.played_card = None
        self.card_visibility = {}

    def lose_lives(self, amount: int) -> None:
        self.lives = max(0, self.lives - amount)
        if self.lives == 0:
            self.active = False

    def to_dict(self, viewer_pid: Optional[str] = None, reveal_hand: bool = False) -> dict:
        """Serializa o jogador para envio via WebSocket.

        viewer_pid: ID de quem está recebendo o estado (para filtrar visibilidade).
        reveal_hand: força revelar todas as cartas (fim de rodada, etc.).
        """
        is_self = viewer_pid == self.pid

        hand_data = []
        for i, card in enumerate(self.hand):
            vis = self.card_visibility.get(i, "self")  # padrão: só o dono vê
            visible = reveal_hand or _card_visible_to(vis, is_self)
            if visible:
                hand_data.append({"index": i, "card": card.to_dict(), "visibility": vis})
            else:
                hand_data.append({"index": i, "card": None, "visibility": vis})

        return {
            "pid": self.pid,
            "nickname": self.nickname,
            "lives": self.lives,
            "active": self.active,
            "connected": self.connected,
            "bet": self.bet,
            "tricks_won": self.tricks_won,
            "hand_size": len(self.hand),
            "hand": hand_data,
            "played_card": self.played_card.to_dict() if self.played_card else None,
        }


def _card_visible_to(visibility: str, is_self: bool) -> bool:
    """Decide se a carta é visível para o receptor.

    visibility values:
      "self"   → apenas o dono vê
      "others" → outros jogadores veem (o dono não vê)
      "none"   → ninguém vê
      "all"    → todos veem (padrão de rodadas normais)
    """
    if visibility == "all":
        return True
    if visibility == "self":
        return is_self
    if visibility == "others":
        return not is_self
    if visibility == "none":
        return False
    return True
