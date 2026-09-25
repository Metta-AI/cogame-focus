# Focus external player check

This draft adds `focus.player.v2`: the game sends a public board, rules,
transcript, and exact legal move IDs to an external player. The player returns
an ID and optional table talk. The game validates the move and owns rules,
results, and replay. Jev calls SystemOne and ranks moves in `focus-player`.
The existing prompt and scripted players use the same game image.

Local check on `linux/amd64`:

```sh
docker build --platform=linux/amd64 -t focus-jev-25001:local .
docker build --platform=linux/amd64 --target build -t focus-jev-25001-build:local .
docker run --rm --platform=linux/amd64 focus-jev-25001-build:local \
  sh -lc 'export PATH=/root/.nimby/nim/bin:$PATH; nim c -r --path:src tests/test_sim.nim && nim c -r -d:release --path:src tests/test_bot.nim'
python3 tools/ci/smoke_jev.py /tmp/focus-jev-smoke-25001
uvx --from 'coworld[auth]==0.1.43' coworld build --project . --version 0.1.99 \
  --compose compose.jev-local.yaml --output dist-jev/coworld_manifest.json
uvx --from 'coworld[auth]==0.1.43' coworld certify \
  dist-jev/coworld_manifest.json --no-open-report --timeout-seconds 120
```

The local compose file used `focus-jev-25001:local` as its image tag. The
native rules and bot suites passed. Two six-ply mixed container episodes
placed Jev in seat 0 and seat 1. The mock made six SystemOne choices; all six
became accepted game moves, with no fallback. Both episodes wrote results
and replay. The normal prompt/scripted fixture passed all ten Coworld
certification checks. The mixed seat-1 replay loaded in the static viewer at
`http://127.0.0.1:39811/index.html?replay=http://127.0.0.1:39811/replay.json`;
clicking the timeline changed the displayed frame from final ply 6 to ply 3.
Seat 0 used a direct mock bearer credential. Seat 1 used the hosted sidecar
environment; all three requests carried `X-Coworld-Player-Slot: 1` and no
bearer header.

These calls used a mock model to check transport and validation. No TypeSafe
credential was available in this session. Gameplay strength, token use,
provider cost, and hosted execution remain unmeasured. No production game
version or hosted policy was released.
