## Export complete Focus games as Metta post-training examples.
## Usage: nim r --path:src tools/export_posttrain.nim OUTPUT GAMES [FIRST_SEED]

import std/[json, os, osproc, strutils]
import focus/[llm, sim]

const OperatorPrompt = "Choose legal moves to maximize your score over the complete game."

when isMainModule:
  let args = commandLineParams()
  if args.len notin 2 .. 3:
    quit("usage: export_posttrain OUTPUT GAMES [FIRST_SEED]", 1)
  let output = args[0]
  let games = parseInt(args[1])
  let firstSeed = if args.len == 3: parseInt(args[2]) else: 1
  if games < 10 or firstSeed < 1:
    quit("at least ten games and a positive first seed are required", 1)
  if dirExists(output) or fileExists(output):
    quit("output already exists: " & output, 1)
  createDir(output)
  let sourceRevision = execProcess("git rev-parse HEAD").strip()
  let manifest = parseFile("coworld_manifest_template.json")
  let variant = manifest["variants"][0]
  doAssert variant["id"].getStr() == "standard"
  var
    trainRows: seq[string]
    validationRows: seq[string]
    runs = newJArray()
  for seed in firstSeed ..< firstSeed + games:
    var config = defaultGameConfig()
    let runtimeConfig = copy(variant["game_config"])
    runtimeConfig["tokens"] = %*["t0", "t1"]
    runtimeConfig["seed"] = %seed
    runtimeConfig["turnDelayMs"] = %0
    config.update($runtimeConfig)
    config = sampleEpisode(config)
    var sim = initSim(config)
    let client = newLlmClient(config)
    var rows: seq[string]
    while not sim.done:
      let seat = sim.turn
      let teacher = client.scriptedAction(sim, seat)
      var completion = %*{"say": teacher.say}
      if teacher.move.kind == mkPlace:
        completion["place"] = %cellName(teacher.move.toCell)
      else:
        completion["move"] = %*{
          "from": cellName(teacher.move.fromCell),
          "count": teacher.move.count,
          "dir": $teacher.move.dir
        }
      let parsed = parseDecision(sim, seat, completion)
      doAssert parsed == teacher
      rows.add($(%*{
        "episode_id": "focus-standard-" & $seed,
        "seed": "focus-standard-" & $seed,
        "decision_id": sim.ply,
        "prompt": [
          {"role": "system", "content": systemPrompt(sim, seat)},
          {"role": "user", "content": userPrompt(sim, seat,
            OperatorPrompt, "Ply " & $(sim.ply + 1) & " of at most " &
              $config.maxPlies & ".")}
        ],
        "completion": [{"role": "assistant", "content": $completion}],
        "game": "focus",
        "action_schema_revision": "focus-move-v1"
      }))
      sim.recordSay(seat, parsed.say)
      sim.applyMove(seat, parsed.move)
    doAssert rows.len > 0 and sim.reason in ["no-moves", "cap"]
    let outcome = sim.resultsJson()
    if seed mod 5 == 0:
      validationRows.add(rows)
    else:
      trainRows.add(rows)
    runs.add(%*{"seed": seed, "decisions": rows.len,
      "scores": outcome["scores"], "reason": sim.reason})
  writeFile(output / "train.jsonl", trainRows.join("\n") & "\n")
  writeFile(output / "validation.jsonl", validationRows.join("\n") & "\n")
  writeFile(output / "manifest.json", pretty(%*{
    "schema_version": 1,
    "game": "focus",
    "variant": "standard",
    "source_revision": sourceRevision,
    "teacher": "scripted-baseline",
    "operator_prompt": OperatorPrompt,
    "train_examples": trainRows.len,
    "validation_examples": validationRows.len,
    "runs": runs
  }) & "\n")
  echo "train=", trainRows.len, " validation=", validationRows.len
