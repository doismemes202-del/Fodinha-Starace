"""
manager.py - Gerenciamento de salas e conexões WebSocket.

Cada sala tem um GameState. O Manager mantém mapeamento de:
  room_id → GameState
  pid → WebSocket

O Manager faz broadcast de estado para todos os jogadores conectados de uma sala.
"""

from __future__ import annotations
import asyncio
import json
import logging
import uuid
from typing import Optional
from fastapi import WebSocket
from .game_state import GameState, Phase

logger = logging.getLogger(__name__)


class RoomManager:
    def __init__(self):
        # room_id → GameState
        self.rooms: dict[str, GameState] = {}
        # pid → WebSocket
        self.connections: dict[str, WebSocket] = {}
        # pid → room_id
        self.pid_to_room: dict[str, str] = {}

    # ------------------------------------------------------------------ #
    # Sala padrão (todos entram na mesma sala "default")
    # ------------------------------------------------------------------ #

    def get_or_create_room(self, room_id: str = "default") -> GameState:
        if room_id not in self.rooms:
            self.rooms[room_id] = GameState(room_id)
        return self.rooms[room_id]

    # ------------------------------------------------------------------ #
    # Conexão / Desconexão
    # ------------------------------------------------------------------ #

    async def connect(self, websocket: WebSocket, pid: str, nickname: str, room_id: str = "default") -> Optional[str]:
        """Conecta um jogador. Retorna erro se não puder entrar."""
        await websocket.accept()
        self.connections[pid] = websocket

        game = self.get_or_create_room(room_id)
        err = game.add_player(pid, nickname)
        if err:
            await self._send(websocket, {"type": "error", "message": err})
            return err

        self.pid_to_room[pid] = room_id
        await self.broadcast_state(room_id)
        return None

    async def disconnect(self, pid: str) -> None:
        room_id = self.pid_to_room.get(pid)
        if room_id and room_id in self.rooms:
            self.rooms[room_id].remove_player(pid)
            await self.broadcast_state(room_id)

        self.connections.pop(pid, None)
        self.pid_to_room.pop(pid, None)

    # ------------------------------------------------------------------ #
    # Processamento de mensagens
    # ------------------------------------------------------------------ #

    async def handle_message(self, pid: str, data: dict) -> None:
        """Processa uma mensagem recebida de um cliente."""
        msg_type = data.get("type")
        room_id = self.pid_to_room.get(pid)
        if not room_id:
            return

        game = self.rooms.get(room_id)
        if not game:
            return

        if msg_type == "start_game":
            err = game.start_game()
            if err:
                await self._send_to_pid(pid, {"type": "error", "message": err})
            else:
                await self.broadcast_state(room_id)

        elif msg_type == "make_bet":
            bet = data.get("bet")
            if bet is None:
                await self._send_to_pid(pid, {"type": "error", "message": "Palpite inválido."})
                return
            err = game.make_bet(pid, int(bet))
            if err:
                await self._send_to_pid(pid, {"type": "error", "message": err})
            else:
                await self.broadcast_state(room_id)

        elif msg_type == "play_card":
            card_index = data.get("card_index")
            if card_index is None:
                await self._send_to_pid(pid, {"type": "error", "message": "Índice inválido."})
                return
            err = game.play_card(pid, int(card_index))
            if err:
                await self._send_to_pid(pid, {"type": "error", "message": err})
            else:
                await self.broadcast_state(room_id)

        elif msg_type == "next_round":
            # Solicitado pelo dealer (ou qualquer jogador) após ROUND_END
            if game.phase == Phase.ROUND_END:
                game.next_round()
                await self.broadcast_state(room_id)

        elif msg_type == "chat":
            text = data.get("text", "")[:200]
            player = game._get_player(pid)
            nick = player.nickname if player else pid
            await self.broadcast(room_id, {
                "type": "chat",
                "nickname": nick,
                "text": text,
            })

    # ------------------------------------------------------------------ #
    # Broadcast
    # ------------------------------------------------------------------ #

    async def broadcast_state(self, room_id: str) -> None:
        """Envia estado personalizado para cada jogador da sala."""
        game = self.rooms.get(room_id)
        if not game:
            return

        tasks = []
        for player in game.players:
            ws = self.connections.get(player.pid)
            if ws and player.connected:
                state = game.to_dict(viewer_pid=player.pid)
                tasks.append(self._send(ws, {"type": "state", "state": state}))

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def broadcast(self, room_id: str, message: dict) -> None:
        game = self.rooms.get(room_id)
        if not game:
            return
        tasks = []
        for player in game.players:
            ws = self.connections.get(player.pid)
            if ws and player.connected:
                tasks.append(self._send(ws, message))
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _send_to_pid(self, pid: str, message: dict) -> None:
        ws = self.connections.get(pid)
        if ws:
            await self._send(ws, message)

    @staticmethod
    async def _send(ws: WebSocket, message: dict) -> None:
        try:
            await ws.send_text(json.dumps(message, ensure_ascii=False))
        except Exception as e:
            logger.warning("Erro ao enviar mensagem: %s", e)


# Instância global
manager = RoomManager()
