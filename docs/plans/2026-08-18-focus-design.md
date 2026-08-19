# Focus (Domination): a stacking board-game coworld

A port of Sid Sackson's **Focus** (published by Parker Brothers as
**Domination**) onto the cogame-parley technology stack: a Nim game server
implementing the Coworld runtime contract, LLM-driven decisions where **a
policy is just a prompt**, an always-legal scripted baseline (a shallow
minimax bot), a shared pure `sim` module driving the server, the tests, and
a static wasm replay viewer, and the parley broadcast chrome (top band,
scorebug, log feed, scrubber, endscreen) around a canvas board.

## Rules ported

- **Board:** an 8×8 grid (files a–h, ranks 1–8) with the three squares in
  each corner removed (a1 b1 a2 · g1 h1 h2 · a8 b8 a7 · g8 h8 h7): 52
  playable squares — a 6×6 centre with 1×4 tabs on each side.
- **Two players**, 18 pieces each, set out on the 6×6 centre (files b–g,
  ranks 2–7) in alternating pairs: ranks 7/5/3 read `R R G G R R`, ranks
  6/4/2 read `G G R R G G` (seat 0 = R, seat 1 = G). Who moves first is
  drawn from the episode seed.
- **Stacks:** pieces stack. A stack is *controlled* by the owner of its
  top piece. On your turn you either **move** or **place**.
- **Move:** pick a stack you control and take its top *k* pieces
  (1 ≤ k ≤ height; you may take fewer than all); move them **exactly k
  squares** in one orthogonal direction, jumping over anything in between.
  The destination must be a playable square. Moved pieces land on top of
  whatever is there. Note only the top piece needs to be yours; the
  sub-stack you carry may contain enemy pieces underneath.
- **Height cap 5:** if a stack exceeds five after a move or a placement,
  pieces are stripped from the **bottom** until it is five: your own
  pieces go to your **reserve**, enemy pieces are **captured** (gone).
- **Place:** instead of moving, put one reserve piece on **any** playable
  square, empty or occupied — it goes on top; the cap applies.
- **End:** a player who cannot move on their turn (controls no stack and
  has no reserve) loses — *the last player able to move wins*. Since every
  playable square has an on-board neighbour, controlling any stack means
  having a legal move.
- **Ply cap (episode budget):** an episode plays at most `maxPlies` plies
  (default 160). At the cap the winner is the side with the greater
  **material** — pieces in the stacks it controls plus its reserve — and
  equal material is a draw. The same rule settles an episode the platform
  deadline stops early.

## Scoring

`scores = [1, 0]` for a win, `[0.5, 0.5]` for a draw. `win` marks the
winner(s). Results also carry `plies`, `reason` (`no-moves`, `cap`,
`deadline`), per-seat `material`, `reserve`, `captured` (enemy pieces
taken), and `first` (which seat moved first).

## Anonymity, hidden information

As in parley/cosino: seats play under anonymous cog aliases drawn from the
seed; policy names never reach a prompt; viewers map aliases back. Focus is
perfect-information, so nothing is redacted — every view sees the whole
board.

## Decisions: LLM with scripted fallback

Per ply the server composes: rules, the board (each occupied square with
its stack bottom→top and its controller), reserves and captures, the
public move history, plus the seat's operator prompt, and asks Claude for
`{"say": "...", "move": {"from": "e4", "count": 2, "dir": "N"}}` or
`{"say": "...", "place": "e4"}`. Every legal move is enumerated in the
prompt (per controlled stack: `e4 h3: 1N e5, 1E f4, 2N e6, …`) so the
model picks rather than derives. Illegal or failed replies fall back to
the scripted bot; no credentials → every seat is scripted so offline
certification completes. Transports ported unchanged (Bedrock sidecar
first, Anthropic API second).

**Scripted baseline** (also a fieldable policy): depth-2 minimax with
alpha-beta over the full legal move list; evaluation = material
difference (controlled pieces + reserve, minus the same for the opponent)
+ captured difference ×2 + mobility (controlled stacks) ×0.5, seeded
random tie-breaks. Fast enough in Nim (~100 moves × 100 replies).

## Player protocol (`focus.player.v1`)

JSON text frames on the Coworld player websocket, identical in shape to
cosino: `prompt` up, `welcome` / `state` / `final` down. Runnables:
`/bin/focus` (game) and `/bin/focus-player` (`PLAYER_PROMPT` env, or
`PLAYER_SCRIPTED=1`).

## Sim module layout

- `src/focus/types.nim` — GameConfig, EventKind, GameEvent, config update.
- `src/focus/sim.nim` — `Board` (52 cells of `seq[int8]` owner stacks),
  `Sim` (board, reserves, captured, turn, ply, done, winner, events),
  legal move generation, `applyMove`/`applyPlace`, end detection, cap
  scoring, `replayMatch` (deterministic: re-applies the recorded moves
  through the same rules to produce one frame per event), JSON.
- Event kinds: `start` (first seat), `say`, `move` (seat, from, to,
  count, carried owners, captured n, reserved n, resulting stack), `place`
  (seat, to, captured/reserved, stack), `end` (reason, winner).

## Viewers

`client/renderer.js`: the parley chrome unchanged (topband, scorebug,
feed, scrubber, endscreen, bubbles, name map); the canvas draws the
52-square board with stacks as offset discs in the seat colours (top disc
on top, height numeral, controller ring), a last-move arrow, cogs beside
the board with reserve/captured tallies. Static wasm viewer
(`replay-viewer/focus_replay.nim`, exports `foc_*`, module
`FocusReplayModule`) re-derives frames with the same sim.

## Episode budgeting

`EpisodeCallBudget = 240` model calls → `maxPlies` capped to it at sample
time; `PlayBudgetFraction` of `COWORLD_TIMEOUT_SECONDS` bounds the clock,
checked every ply (a part-played ply has no side effects, unlike a hand).

## Out of scope (v1)

3- and 4-player Focus, the "capture N pieces" alternate ending, opening
piece swaps, time controls.
