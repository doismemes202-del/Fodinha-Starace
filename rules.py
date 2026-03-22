"""
rules.py - Regras de Vira, manilha, hierarquia de força e visibilidade de cartas.
"""

from __future__ import annotations
import random
from typing import Optional
from .cards import (
    Card, JOKER, shuffled_deck, get_manilha_value, card_strength,
    SUIT_ORDER, SUIT_RANK
)
from .player import Player

# Ciclo de cartas por rodada (índice 0 = rodada 1)
ROUND_CARD_COUNTS = [1, 2, 3, 4, 5, 6, 7, 8, 7, 6, 5, 4, 3, 2, 1]


def cards_for_round(round_number: int) -> int:
    """Retorna quantas cartas cada jogador recebe na rodada (1-indexed).
    Cicla se ultrapassar 15.
    """
    idx = (round_number - 1) % len(ROUND_CARD_COUNTS)
    return ROUND_CARD_COUNTS[idx]


def deal_cards(
    players: list[Player],
    round_number: int,
) -> tuple[Card, list[Card], bool]:
    """Distribui cartas e determina o Vira.

    Retorna:
        vira: a carta Vira
        extra_viras: lista de viras extras (quando vira foi JOKER)
        vira_was_joker: True se o primeiro vira tirado foi JOKER
    """
    n_cards = cards_for_round(round_number)
    n_players = len(players)

    deck = shuffled_deck()

    # Determinar Vira (pode ser múltiplo se cair JOKER)
    extra_viras: list[Card] = []
    vira_was_joker = False

    vira = deck.pop(0)
    while vira.is_joker:
        # JOKER como vira: fica inutilizável, abre outro
        extra_viras.append(vira)
        vira_was_joker = True
        if not deck:
            break
        vira = deck.pop(0)

    # Ajustar quantidade caso baralho insuficiente
    available = len(deck)
    max_cards = available // n_players
    actual_cards = min(n_cards, max_cards)

    for player in players:
        player.reset_round()
        player.hand = [deck.pop(0) for _ in range(actual_cards)]
        _apply_visibility(player, round_number, actual_cards)

    return vira, extra_viras, vira_was_joker


def _apply_visibility(player: Player, round_number: int, n: int) -> None:
    """Define a visibilidade das cartas conforme regras especiais de rodada."""
    idx = (round_number - 1) % len(ROUND_CARD_COUNTS)
    actual_round_pos = idx + 1  # posição no ciclo (1-15)

    if actual_round_pos == 1:
        # Rodada 1 (1 carta): jogador não vê a própria, mas todos os outros veem
        for i in range(n):
            player.card_visibility[i] = "others"

    elif actual_round_pos == 3:
        # Rodada 3 (3 cartas): 1 só o dono vê, 1 ninguém vê, 1 só os outros veem
        indices = list(range(n))
        random.shuffle(indices)
        vis_types = ["self", "none", "others"]
        for i, vis in zip(indices[:3], vis_types[:n]):
            player.card_visibility[i] = vis

    else:
        # Demais rodadas: todos veem normalmente (o dono inclusive)
        for i in range(n):
            player.card_visibility[i] = "all"


def resolve_trick(
    plays: list[tuple[Player, Card]],
    manilha_value: str,
    vira_was_joker: bool,
) -> Player:
    """Determina quem vence a vaza.

    plays: lista de (jogador, carta) na ordem em que jogaram.
    Retorna o jogador vencedor.
    """
    best_player, best_card = plays[0]
    best_strength = card_strength(best_card, manilha_value, vira_was_joker)

    for player, card in plays[1:]:
        strength = card_strength(card, manilha_value, vira_was_joker)

        # Lógica especial do JOKER vs ZAP
        if card.is_joker and _is_zap(best_card, manilha_value):
            # JOKER ganha do ZAP (matazap) — apenas se vira não foi JOKER
            if not vira_was_joker:
                best_player = player
                best_card = card
                best_strength = strength
            # se vira_was_joker, ZAP é invencível → JOKER perde
            continue

        if best_card.is_joker and _is_zap(card, manilha_value):
            # Carta atual é ZAP; se vira foi JOKER, ZAP bate o JOKER
            if vira_was_joker:
                best_player = player
                best_card = card
                best_strength = strength
            continue

        if strength > best_strength:
            best_player = player
            best_card = card
            best_strength = strength

    return best_player


def _is_zap(card: Card, manilha_value: str) -> bool:
    """Verifica se a carta é o ZAP (manilha de Paus)."""
    return card.value == manilha_value and card.suit == "P"


def validate_bet(
    bet: int,
    n_cards: int,
    bets_so_far: list[int],
    is_dealer: bool,
    n_players: int,
) -> Optional[str]:
    """Valida um palpite.

    Retorna None se válido, ou mensagem de erro.
    """
    if bet < 0 or bet > n_cards:
        return f"Palpite inválido: deve ser entre 0 e {n_cards}."

    total_so_far = sum(bets_so_far)

    if is_dealer:
        # Dealer não pode fazer a soma total igual a N
        if total_so_far + bet == n_cards:
            return "Como Dealer, você não pode fazer a soma dos palpites igual ao número de cartas."
        # Dealer só pode palpitar ≥1 se algum outro já apostou ≥1
        if bet >= 1 and all(b == 0 for b in bets_so_far):
            return "Como Dealer, você só pode palpitar ≥1 se outro jogador já palpitou ≥1."
    else:
        # Regra global: soma total não pode ser igual a N
        # (quando for o último a apostar antes do dealer, checamos aqui)
        remaining = n_players - len(bets_so_far) - 1  # jogadores que ainda vão apostar após este
        if remaining == 0 and total_so_far + bet == n_cards:
            return "Este palpite tornaria a soma igual ao número de cartas. Não é permitido."

    return None


def is_final_duel_round(n_active: int) -> bool:
    """Retorna True se devemos jogar o Duelo Final (2 jogadores ativos)."""
    return n_active == 2
