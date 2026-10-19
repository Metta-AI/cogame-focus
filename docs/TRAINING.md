# Focus training

Five training wordings (`canonical`, `plain`, `numbered`, `questions`,
`reordered`) vary identity, stack control, movement, overflow, reserve drops,
and endings. The v2 bank preserves board coordinates, game facts, strategic
permissions, action grammar, and canonical messages. `mixed` resolves
an explicit nonnegative `promptSeed % 5`, independently of game and teacher
randomness. Selection stays fixed throughout an episode. `heldout-briefing`
and `heldout-reference` are evaluation-only.

## Collection

The persistent bridge accepts `MANIFEST [VARIANT [text]]`. Text mode retains
full move/drop actions and public speech through the production parser. Reset
accepts `promptVariant`, `promptSeed`, and `split`; held-out training is rejected.
Private metadata records exact message hashes, bank, wording, and seed.
Numeric mode retains its 331 features and 1,344 action slots.

Export complete teacher games from a clean committed checkout:

```sh
nim c -d:release --path:src -o:/tmp/focus-export tools/export_posttrain.nim
/tmp/focus-export /tmp/focus-examples 10 1 mixed 0
```

The scripted tactician plays ordinary published games, up to 120 plies, with
normal early endings. Exports retain the original `train.jsonl`,
`validation.jsonl`, and `manifest.json` format, with exact messages and
wording metadata. Every teacher move passes the production parser unchanged
and is applied by the engine.

Mixed selection cycles through the five training wordings once per game.
Seed families exclude wording; multiples of five enter validation.
Output directories are private. Existing destinations, fewer than ten games,
and held-out wordings are rejected.

## Validation

```sh
python3 tools/test_prompt_games.py /tmp/focus-bridge
python3 tools/test_export_posttrain.py /tmp/focus-export
```

The wording workflow runs 19 complete games, including speech normalization
and reserve drops. The export workflow runs ten games and checks seed-family
separation and move grammar. These checks establish mechanics and protocol
behavior, not improved learning or resistance to policy collapse.
This repository has no CI workflow.
