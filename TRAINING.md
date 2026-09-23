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
