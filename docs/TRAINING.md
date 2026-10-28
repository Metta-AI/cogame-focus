# Focus training

## Native real-model capture

Use the production game and `/bin/focus-player` with `PLAYER_PROMPT`, omitting
`PLAYER_SCRIPTED`. The platform supplies the existing game-owned LLM sidecar.
Set the game's private `COGAME_SAVE_TRAJECTORY_URI` destination; absent a
destination, capture is disabled.

Capture retains actual request bodies, exposed call-ID headers, received
response bodies, retries and the frozen pre-move public board with the acting
seat's private operator prompt. It joins these to the actual applied move and
speech. Native parser normalization, scripted fallback and engine-rejected
proposals cannot become real-model targets. Unattributed external actions stay
unknown; missing usage, model/token identities and likelihoods are not invented.
Inference, legality checks, the tactician fallback, pacing and rules remain
unchanged. Use `collect-hosted`, `prepare-hosted-data` and SLIME through the
research package for authenticated receipt admission and token/mask checks.

The opening board is fixed. Seeds affect aliases and the first mover, not a
fresh random board. Native capture groups physical families by initial board,
first mover and actual sampled ply cap; alias-only seeds and wording changes
share one family. Do not count repeated aliases as independent scenarios.
The two first-mover configurations are limited opening strata, not broad
physical generalization. Historical scripted exports retain their old labels.

Run the complete native system fixture with production binaries:

```sh
nim c -d:release --path:src -o:/tmp/focus src/focus.nim
nim c -d:release --path:src -o:/tmp/focus-player src/focus_player.nim
python3 tools/test_native_capture.py /tmp/focus /tmp/focus-player /tmp/focus-native-capture
```

Eight full 120-ply games check capture on/off replay and outcome equality,
retries, fallback, normalized speech, private operator isolation, missing usage,
offline no-evidence fallback and family equality across alias-only seeds.
Fixture replies are synthetic software evidence, never training teachers.
Output directories must be new. Capture alone does not establish teacher
strength, online RL readiness or hosted learned-checkpoint parity.

## Historical scripted training

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

Mixed selection cycles through the five training wordings separately within each
split. Episode IDs include requested selection, resolved wording, and prompt seed
to distinguish matched collections.
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
