# Focus training

Five training introductions (`canonical`, `plain`, `numbered`, `questions`,
`reordered`) preserve shared rules and canonical messages. `mixed` resolves
an explicit nonnegative `promptSeed % 5`, independently of game and teacher
randomness. Selection stays fixed throughout an episode. `heldout-briefing`
and `heldout-reference` are evaluation-only.

## Collection

The persistent bridge accepts `MANIFEST [VARIANT [text]]`. Text mode retains
full move/drop actions and public speech through the production parser. Reset
accepts `promptVariant`, `promptSeed`, and `split`; held-out training is rejected.
Private metadata records exact message hashes, bank, wording, and seed.
Numeric mode retains its 331 features and 1,344 action slots.

Export complete candidate episodes from a clean committed checkout:

```sh
nim c -d:release --path:src -o:/tmp/focus-export tools/export_posttrain.nim
/tmp/focus-export /tmp/focus-candidates 10 1 standard canonical 0
```

The scripted tactician plays ordinary published games, up to 120 plies, with
normal early endings. Private `trajectories.jsonl`, `execution.jsonl`, and
`manifest.json` retain source revision, exact messages, teacher proposals,
installed moves and speech, event intervals, resulting boards, and outcomes.
Teacher attempts contain no inference request, platform call ID, or behavior
log probabilities. Files use private permissions.

These are candidates, not automatically admitted labels. Convert through
Coworld's `export_complete_episodes`, then use Metta's independent source-hash
review gate before training export. Keep each `focus-SEED` family together
across wordings. Existing destinations, fewer than ten games, and held-out
exports are rejected. No automatic train/validation files are emitted.

## Native evidence and checks

Set `FOCUS_HOST_TRACE_PATH`, `FOCUS_ATTEMPT_TRACE_DIR`, and
`FOCUS_SOURCE_REVISION` to record private native evidence. Actual request bodies,
retry messages, raw responses, failures, proposals, installed actions, and replay
event intervals remain separate. External-player decisions also record installed
actions and their actual origin. Public replays retain their existing format.

```sh
python3 tools/test_prompt_games.py /tmp/focus-bridge /tmp/original-focus-bridge
python3 tools/test_export_posttrain.py /tmp/focus-export
python3 tools/test_native_prompts.py /tmp/focus-game /tmp/focus-player /tmp/focus-native
```

The text panel runs 25 complete games and two original numeric comparisons.
The source panel runs ten games. The native panel runs eight published cases
with two real players and a reserved closed inference endpoint; `--smoke`
runs canonical only. It retains the published 120-ply cap and pacing.
These checks establish execution and provenance, not successful provider
inference or improved learning. This repository currently has no CI workflow.
