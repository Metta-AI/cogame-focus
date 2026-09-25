# Focus

Sid Sackson's **Focus** (Parker Brothers' **Domination**) for the Softmax
Coworld platform, on the
[cogame-parley](https://github.com/Metta-AI/cogame-parley) technology
stack. Two cogs, an 8×8 board with the three squares in each corner
missing (52 squares), 18 pieces each. Pieces stack; whoever owns the top
piece controls the stack. Move the top *k* pieces of a stack you control
exactly *k* squares orthogonally and land on whatever is there; stacks
over five shed from the bottom (your own to your reserve, enemy pieces
captured); drop a reserve piece anywhere instead of moving. **The last
player able to move wins**; the ply cap settles on material.

Players can register a prompt, the built-in scripted tactician, or an
external action policy over `focus.player.v2`. Each acting external player
receives the public board, rules, and exact legal move IDs, then returns a
move ID and optional table talk. The game validates and applies the move.
`PLAYER_JEV=1` runs Jev in the player container, where it ranks the legal
moves. Prompt players retain the original game-hosted Claude path. The
**scripted baseline** uses two-ply minimax on material, captures, and
mobility; it also covers missing model credentials and timed-out actions.

Seats play under **anonymous cog names** (Sprocket, Gizmo, …): policy
display names never reach the agents' prompts, so nobody can meta-game
"that seat is the champion". The spectator and replay viewers map the
aliases back to policy names; results are reported under policy names.

## Layout

- `src/focus.nim` — entrypoint (Coworld runtime contract, live vs replay mode)
- `src/focus/sim.nim` — pure rules: board, moves, cap, reserve, endings,
  replay derivation; shared by server, tests, and the wasm viewer
- `src/focus/llm.nim` — Claude client + the scripted baseline bot
- `src/focus/server.nim` — mummy HTTP/WS server (player, global, replay)
- `src/focus_player.nim` — prompt, scripted, and Jev player entrypoint
- `src/focus/jev_policy.nim` — Jev request and legal-move ranking
- `client/` — shared canvas renderer + global/player/replay pages (the
  parley broadcast chrome around a Focus board)
- `replay-viewer/` — static wasm replay viewer (`?replay=<url>`)
- `tools/build_replay_viewer.sh` — Coworld replay-viewer build hook
- `data/` — cog sprites and art, borrowed from
  [coworld-ctf](https://github.com/Metta-AI/coworld-ctf) (MIT)
- `docs/plans/` — the design note this port was built from

## Local loop

```bash
export PATH="$HOME/.nimby/nim/bin:$PATH"
nimby --global sync nimby.lock                 # fetch pinned packages
# Generate nim.cfg from your nimby package tree (not committed - the
# paths are machine-specific):
rm -f nim.cfg
for pkg in ~/.nimby/pkgs/*; do
  if [ -d "$pkg/src" ]; then echo "--path:\"$pkg/src\"" >> nim.cfg;
  else echo "--path:\"$pkg\"" >> nim.cfg; fi
done
echo '--path:"src"' >> nim.cfg

nim r --path:src tests/test_sim.nim            # rules tests
nim r -d:release --path:src tests/test_bot.nim # scripted-baseline tests
nim c -d:release -o:bin/focus src/focus.nim
nim c -d:release -o:bin/focus-player src/focus_player.nim
# See tmp/config.json for a two-seat fixture; run with COGAME_* env + 2
# players. Export ANTHROPIC_API_KEY for real Claude play; omit for the
# scripted baseline.
```

Coworld packaging (from a metta checkout):

```bash
uv run coworld build --project <this dir> --version 0.1.x
uv run coworld certify <this dir>/dist/coworld_manifest.json
uv run coworld upload-coworld <this dir>/dist/coworld_manifest.json
uv run coworld secret put focus anthropic_api_key <keyfile>   # hosted Claude
```

## Fielding a policy

```bash
uv run coworld upload-policy <focus image> --name my-focus \
  --run /bin/focus-player \
  --secret-env PLAYER_PROMPT="Your Focus strategy here."
```

Field the scripted tactician with `--env PLAYER_SCRIPTED=1`, or Jev with
`--env PLAYER_JEV=1` and a player-scoped TypeSafe credential or hosted
inference sidecar. `PLAYER_PROMPT` gives Jev optional strategy guidance.
The Jev credential belongs to the player policy, not the game.

To check the player path without a provider credential, build the image and
run `python3 tools/ci/smoke_jev.py /tmp/focus-jev-smoke`. The smoke runs Jev
in each seat against the scripted tactician, serves a mock SystemOne response,
and checks accepted actions, results, and replay. It does not measure Jev
strategy or provider cost.
