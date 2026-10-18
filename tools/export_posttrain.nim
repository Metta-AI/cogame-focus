## Complete private candidates; independent review owns training admission.
import std/[json, os, osproc, strutils]
import focus/[llm, sim, prompts, evidence]

const OperatorPrompt = "Choose legal moves to maximize your score over the complete game."

when isMainModule:
  let args = commandLineParams()
  if args.len notin [2, 3, 4, 6]:
    quit("usage: export_posttrain OUTPUT GAMES [FIRST_SEED] [VARIANT [PROMPT_VARIANT PROMPT_SEED]]", 1)
  let output = absolutePath(args[0])
  let games = parseInt(args[1])
  let firstSeed = if args.len >= 3: parseInt(args[2]) else: 1
  let variant = if args.len >= 4: args[3] else: "standard"
  doAssert variant == "standard" and games >= 10 and firstSeed >= 1
  let selection = promptSelection(if args.len == 6:
    %*{"promptVariant": args[4], "promptSeed": parseInt(args[5])} else: newJObject())
  if selection.selectedVariant in {pvHeldoutBriefing, pvHeldoutReference}:
    raise newException(ValueError, "held-out wording is evaluation-only")
  doAssert not dirExists(output) and not fileExists(output)
  let status = execCmdEx("git status --porcelain")
  doAssert status.exitCode == 0 and status.output.strip().len == 0,
    "Commit qualified source before generating a pinned candidate corpus"
  let head = execCmdEx("git rev-parse HEAD")
  doAssert head.exitCode == 0
  let revision = head.output.strip()
  let manifest = parseFile("coworld_manifest_template.json")
  let variantConfig = manifest["variants"][0]
  doAssert variantConfig["id"].getStr() == variant
  writePrivate(output / "trajectories.jsonl", "")
  writePrivate(output / "execution.jsonl", "")
  let stream = open(output / "trajectories.jsonl", fmAppend)
  let execution = open(output / "execution.jsonl", fmAppend)
  var runs = newJArray()
  try:
    for seed in firstSeed ..< firstSeed + games:
      var config = defaultGameConfig()
      let runtimeConfig = copy(variantConfig["game_config"])
      runtimeConfig["tokens"] = %*["t0", "t1"]
      runtimeConfig["seed"] = %seed
      config.update($runtimeConfig)
      config = sampleEpisode(config)
      var world = initSim(config)
      let client = newScriptedClient(config)
      let family = "focus-" & $seed
      let episode = family & "-" & variant & "-" & $selection.selectedVariant & "-" & $selection.seed
      while not world.done:
        let seat = world.turn
        let id = world.ply
        let system = systemPrompt(world, seat, selection)
        let user = userPrompt(world, seat, OperatorPrompt,
          "Ply " & $(world.ply + 1) & " of at most " & $config.maxPlies & ".")
        let messages = %*[{"role": "system", "content": system}, {"role": "user", "content": user}]
        let observation = world.tableStateJson()
        observation["prompt_template"] = selection.promptMetadata(system, user)
        let teacher = client.scriptedAction(world, seat)
        let proposal = decisionJson(teacher)
        let parsed = parseDecision(world, seat, proposal)
        let eventStart = world.events.len
        world.recordSay(seat, parsed.say)
        world.applyMove(seat, parsed.move)
        let installed = world.installedAction(eventStart)
        let accepted = proposal == installed
        let attemptId = $id & "-teacher"
        stream.writeLine($(%*{
          "schema_version": "1", "event_type": "decision", "episode_id": episode,
          "decision_id": $id, "decision_index": id, "game": "focus",
          "game_version": "source-" & revision, "source_revision": revision,
          "seat": $seat, "visibility": "private", "observation": observation,
          "prompt": (if accepted: messages else: newJNull()),
          "attempts": [{"attempt_id": attemptId, "policy": "scripted-baseline", "origin": "teacher",
            "inference_mode": "text_action", "prompt": messages,
            "response": $proposal, "parsed_action": proposal, "accepted": accepted,
            "request": newJNull(), "platform_call_id": newJNull(), "behavior_logprobs": newJNull(),
            "rejection_reason": (if accepted: newJNull() else: %"engine-normalized-submission")}],
          "selected_attempt_id": (if accepted: %attemptId else: newJNull()),
          "executed_action": installed, "action_status": (if accepted: "accepted" else: "fallback"),
          "fallback_origin": (if accepted: newJNull() else: %"engine-normalized-submission"),
          "terminal": world.done}))
        var events = newJArray()
        for index in eventStart ..< world.events.len: events.add(eventToJson(world.events[index]))
        execution.writeLine($(%*{
          "schema_version": 1, "event_type": "decision_execution", "episode_id": episode,
          "decision_id": $id, "source_revision": revision, "visibility": "private",
          "seat": seat, "turn": id, "event_start": eventStart, "event_end": world.events.len,
          "events": events, "installed_action": installed,
          "resulting_state": world.tableStateJson(), "terminal": world.done}))
      doAssert world.reason in ["no-moves", "cap"]
      let outcome = world.resultsJson()
      var participants = newJObject()
      for seat in 0 ..< Seats: participants[$seat] = %*{"score": outcome["scores"][seat]}
      stream.writeLine($(%*{
        "schema_version": "1", "event_type": "episode", "episode_id": episode,
        "seed_family": family, "game": "focus", "game_version": "source-" & revision,
        "source_revision": revision, "status": "completed", "outcome": outcome,
        "participant_outcomes": participants}))
      runs.add(%*{"seed": seed, "decisions": world.ply, "scores": outcome["scores"], "reason": world.reason})
  finally:
    execution.close()
    stream.close()
  writePrivate(output / "manifest.json", pretty(%*{
    "schema_version": 1, "game": "focus", "variant": variant,
    "source_revision": revision, "teacher": "scripted-baseline",
    "prompt_selection": selection.selectionMetadata(),
    "split_authority": "shared Coworld SDK and application importer by seed_family",
    "execution_evidence": "execution.jsonl", "runs": runs}) & "\n")
  echo "complete games=", games
