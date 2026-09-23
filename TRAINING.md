# Metta post-training data

The native simulator and published scripted policy export supervised examples
for the certified Focus variant:

```sh
nimby sync nimby.lock
nim r -d:release --path:src tools/export_posttrain.nim \
  /tmp/focus-standard 10 1
```

The exporter reads the variant configuration from the Coworld manifest, adds
the per-seat tokens supplied by the hosted platform, and plays complete
seeded games without spectator delays. At each turn, it records the acting
seat's hosted system and user prompts and a scripted move accepted by the
game's reply parser. The parsed move advances the native simulator. Whole
games stay in one split. The output manifest records source revision, scores,
ending reason, and row counts. Existing output directories are never
overwritten.

Train the output with Metta post-training:

```sh
nix develop -c uv run --package metta-posttrain --extra train \
  python -m metta_posttrain.train --dataset /tmp/focus-standard \
  --output /tmp/focus-adapter --model Qwen/Qwen3-0.6B \
  --max-steps 100 --max-length 4096
```

Ten complete games yielded 884 training and 240 validation examples. All
1,124 examples fit the Qwen2.5-0.5B-Instruct tokenizer in 4,096 tokens; the
maximum was 1,786. These examples distill the scripted teacher; they do not
establish stronger league play. One CPU optimizer step with a local tiny model
included every example and reduced heldout loss, verifying the Metta
post-training path.

# Numeric reinforcement learning

Compile the persistent bridge and pass its manifest to Metta's
`recipes.external.coworld.train` (native PufferLib) or
`recipes.external.coworld_metta_rl.train` (Metta RL):

```sh
nim c -d:release --path:src -o:/tmp/focus-train-bridge tools/train_bridge.nim
python tools/test_train_bridge.py /tmp/focus-train-bridge
```

The certified standard variant has two seats, 331 numeric observation values,
and 1,344 fixed action slots: each playable stack origin, carry size 1–5 and
orthogonal direction, plus a reserve drop on each square. Illegal choices
are masked by the simulator's legal-move list. The numeric observation is the
public board, reserves, captures, seat and ply. Text messages retain the
hosted prompts and legal-move list for Metta post-training. The seeded
minimax baseline supplies opponents and teacher labels. A complete game
returns its native win/draw/loss scores.
