# 🃏 Fodinha Online

Jogo de cartas multiplayer online estilo **Fodinha** (truco/fodinha),
com backend em **FastAPI (Python)** e frontend web **mobile-first**.

---

## Requisitos

- Python 3.10+
- Navegador moderno (Chrome, Firefox, Edge, Safari)

---

## Instalação e execução rápida

```bash
# 1. Entre na pasta do projeto
cd fodinha_game

# 2. Crie um ambiente virtual
python -m venv .venv

# 3. Ative o ambiente virtual
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

# 4. Instale as dependências
pip install -r requirements.txt

# 5. Inicie o servidor
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abra o navegador em: **http://localhost:8000**

Para jogar com amigos na mesma rede, use o IP da sua máquina:
`http://192.168.x.x:8000`

---

## Estrutura do projeto

```
fodinha_game/
├── main.py               # Servidor FastAPI (HTTP + WebSocket)
├── requirements.txt
├── README.md
├── game/
│   ├── __init__.py
│   ├── cards.py          # Baralho, cartas, JOKER, hierarquia
│   ├── rules.py          # Vira, manilha, força, visibilidade, validação
│   ├── player.py         # Modelo de jogador (mão, vidas, palpite)
│   ├── game_state.py     # Máquina de estados da partida
│   └── manager.py        # Gerenciamento de salas e WebSockets
└── static/
    ├── index.html        # Interface SPA (lobby + partida)
    ├── style.css         # Layout mobile-first
    └── game.js           # Lógica do cliente WebSocket
```

---

## Regras implementadas

### Baralho
- Valores: `4 5 6 7 Q J K A 2 3` (8, 9 e 10 **não** fazem parte)
- Naipes: Ouros ♦ < Espadas ♠ < Copas ♥ < Paus ♣
- **JOKER** (As de Estrela): mais fraca de todas — exceto contra o ZAP (matazap)

### Vira e Manilha
- Após distribuir, a carta do topo do monte é o **Vira**
- A manilha é a carta de valor imediatamente seguinte na hierarquia
- Manilhas por naipe: Ouros (Picafumo) < Espadas (Espadilha) < Copas (Copeta) < Paus (ZAP)
- Se o **Vira for JOKER**: fica inutilizável, abre novo Vira; ZAP fica invencível nessa rodada

### Ciclo de rodadas (número de cartas por jogador)
```
1 → 2 → 3 → 4 → 5 → 6 → 7 → 8 → 7 → 6 → 5 → 4 → 3 → 2 → 1 → (reinicia)
```

### Visibilidade especial
- **Rodada 1** (1 carta): o dono não vê a própria carta; adversários veem
- **Rodada 3** (3 cartas): 1 só o dono vê / 1 ninguém vê / 1 só os outros veem
- **Rodada 6** (6 cartas): Vira fica oculto até todos apostarem
- Demais rodadas: cada um vê normalmente suas cartas

### Palpites
- Cada jogador aposta quantas vazas acha que vai ganhar (0 a N)
- **Restrição do Dealer**: não pode fazer a soma dos palpites igual a N
- Restrição do Dealer adicional: só pode palpitar ≥1 se outro já apostou ≥1
- Ordem: à direita do Dealer → horário → Dealer por último

### Vidas
- Cada jogador começa com **5 vidas**
- Errou o palpite: perde `|X − Y|` vidas
- Acertou: não perde nada
- Com 0 vidas: eliminado

### Duelo Final
- Quando restam 2 jogadores: rodada especial de **6 cartas** com Vira oculto durante palpites
- Vence quem tiver mais vidas ao final
- Empate: duelo se repete

---

## Protocolo WebSocket

### Cliente → Servidor
| Tipo | Campos | Descrição |
|------|--------|-----------|
| `start_game` | — | Inicia a partida |
| `make_bet` | `bet: int` | Registra palpite |
| `play_card` | `card_index: int` | Joga carta da mão |
| `next_round` | — | Avança para próxima rodada (após ROUND_END) |
| `chat` | `text: str` | Mensagem de chat |

### Servidor → Cliente
| Tipo | Conteúdo |
|------|----------|
| `connected` | `pid`, `nickname` atribuídos |
| `state` | Estado completo personalizado por jogador |
| `chat` | `nickname`, `text` |
| `error` | `message` de erro |

---

## Tecnologias

- **FastAPI** – framework web assíncrono
- **uvicorn** – servidor ASGI
- **WebSockets** – comunicação em tempo real (nativo do FastAPI)
- **HTML + CSS + JavaScript** – frontend vanilla, sem build step
