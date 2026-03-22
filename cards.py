"""
cards.py - Definições de cartas e baralho para o jogo Fodinha.

Hierarquia de valores: 4 < 5 < 6 < 7 < Q < J < K < A < 2 < 3
Hierarquia de naipes:  Ouros < Espadas < Copas < Paus
Carta especial: JOKER (As de Estrela) - mais fraca de todas, exceto contra ZAP.
Cartas 8, 9 e 10 NÃO são utilizadas.
"""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional

# Ordem crescente de força dos valores
VALUE_ORDER = ["4", "5", "6", "7", "Q", "J", "K", "A", "2", "3"]
VALUE_RANK = {v: i for i, v in enumerate(VALUE_ORDER)}

# Hierarquia de naipes (Ouros=0 mais fraco, Paus=3 mais forte)
SUIT_ORDER = ["O", "E", "C", "P"]   # Ouros, Espadas, Copas, Paus
SUIT_RANK  = {s: i for i, s in enumerate(SUIT_ORDER)}

SUIT_NAMES = {"O": "Ouros", "E": "Espadas", "C": "Copas", "P": "Paus", "J": "Estrela"}

MANILHA_NAMES = {
    "O": "Picafumo",
    "E": "Espadilha",
    "C": "Copeta",
    "P": "ZAP",
}


@dataclass(frozen=True)
class Card:
    """Representa uma carta do baralho.

    value: "4"–"3" ou "JOKER"
    suit: "O" | "E" | "C" | "P" | "J" (apenas para JOKER)
    """

    value: str
    suit: str

    # ------------------------------------------------------------------ #
    @property
    def is_joker(self) -> bool:
        return self.value == "JOKER"

    @property
    def display_name(self) -> str:
        if self.is_joker:
            return "JOKER (As de Estrela)"
        return f"{self.value} de {SUIT_NAMES[self.suit]}"

    @property
    def short_name(self) -> str:
        if self.is_joker:
            return "JK"
        return f"{self.value}{self.suit}"

    def to_dict(self) -> dict:
        return {
            "value": self.value,
            "suit": self.suit,
            "display": self.display_name,
            "short": self.short_name,
            "is_joker": self.is_joker,
        }


# Singleton joker
JOKER = Card("JOKER", "J")


def build_deck() -> list[Card]:
    """Cria um baralho completo (40 cartas normais + 1 JOKER = 41 cartas)."""
    cards: list[Card] = []
    for value in VALUE_ORDER:
        for suit in SUIT_ORDER:
            cards.append(Card(value, suit))
    cards.append(JOKER)
    return cards


def shuffled_deck() -> list[Card]:
    """Retorna um baralho embaralhado."""
    deck = build_deck()
    random.shuffle(deck)
    return deck


def next_value(value: str) -> str:
    """Retorna o próximo valor na hierarquia (para calcular a manilha).
    Cicla: após '3' vem '4'.
    """
    idx = VALUE_RANK[value]
    return VALUE_ORDER[(idx + 1) % len(VALUE_ORDER)]


def get_manilha_value(vira: Card) -> str:
    """Dado o Vira, retorna o valor da manilha (próximo na hierarquia)."""
    if vira.is_joker:
        # Se o vira for JOKER, este caso é tratado no game_state antes de chamar aqui.
        # Por segurança, retorna "4" (menor valor).
        return "4"
    return next_value(vira.value)


def card_strength(card: Card, manilha_value: str, vira_was_joker: bool) -> tuple[int, int]:
    """Retorna uma tupla (categoria, rank) para comparar cartas.

    Categorias:
      0 = JOKER (mais fraca em geral)
      1 = carta comum
      2 = manilha

    Dentro de manilhas, rank = SUIT_RANK[suit]  (0-3)
    Dentro de comuns, rank = VALUE_RANK[value] * 4 + SUIT_RANK[suit]
    JOKER tem rank = -1 (sempre perde exceto contra ZAP)
    """
    if card.is_joker:
        return (0, -1)

    if card.value == manilha_value:
        return (2, SUIT_RANK[card.suit])

    # Carta comum
    rank = VALUE_RANK[card.value] * 4 + SUIT_RANK[card.suit]
    return (1, rank)
