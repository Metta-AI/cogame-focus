## Persistent JSONL bridge for Metta RL and native Puffer training.
## nim c -d:release --path:src -o:focus-train-bridge tools/train_bridge.nim
## focus-train-bridge coworld_manifest_template.json [standard]

import std/[json, os]
import focus/[llm, sim]

const
  OperatorPrompt = "Choose legal moves to maximize your score over the complete game."
  MoveSlots = Cells * StackCap * 4
  ActionSlots = MoveSlots + Cells

proc seedOf(value: string): int =
  var hash = 2166136261'u32
  for ch in value:
    hash = (hash xor uint32(ord(ch))) * 16777619'u32
  int(hash and 0x7fffffff'u32)

proc actionOf(move: Move): JsonNode =
  if move.kind == mkPlace:
    %*{"place": cellName(move.toCell)}
  else:
    %*{"move": {"from": cellName(move.fromCell),
      "count": move.count, "dir": $move.dir}}

proc decision(game: Sim, id: int): JsonNode =
  let seat = game.turn
  %*{
    "kind": "decision", "game": "focus", "decision_id": id,
    "seat": seat, "engine_seat": seat, "turn": game.ply,
    "semantic_view": {
      "seat": seat, "ply": game.ply, "max_plies": game.config.maxPlies,
      "board": game.board, "reserve": game.reserve,
      "captured": game.captured
    },
    "inbox": [],
    "messages": [
      {"role": "system", "content": systemPrompt(game, seat)},
      {"role": "user", "content": userPrompt(game, seat, OperatorPrompt,
        "Ply " & $(game.ply + 1) & " of at most " & $game.config.maxPlies & ".")}
    ],
    "speech_messages": [],
    "action_schema": {
      "type": "object", "oneOf": [
        {"required": ["place"]}, {"required": ["move"]}
      ]
    },
    "typed_question": newJNull()
  }

proc encoding(game: Sim, id: int): JsonNode =
  let seat = game.turn
  var values = newJArray()
  for other in 0 ..< Seats:
    values.add(%(if seat == other: 1 else: 0))
  for value in [game.ply, game.config.maxPlies, game.first]:
    values.add(%value)
  for other in 0 ..< Seats:
    for value in [game.reserve[other], game.captured[other],
        game.material(other)]:
      values.add(%value)
  for cell in 0 ..< Cells:
    for level in 0 ..< StackCap:
      values.add(%(if level < game.board[cell].len:
        game.board[cell][level] else: -1))
  var legal: array[ActionSlots, bool]
  for move in game.legalMoves(seat):
    let slot =
      if move.kind == mkPlace: MoveSlots + move.toCell
      else: move.fromCell * StackCap * 4 + (move.count - 1) * 4 + ord(move.dir)
    legal[slot] = true
  var actions = newJArray()
  for cell in 0 ..< Cells:
    for count in 1 .. StackCap:
      for dir in Direction:
        let slot = cell * StackCap * 4 + (count - 1) * 4 + ord(dir)
        if legal[slot]:
          actions.add(actionOf(Move(kind: mkMove, fromCell: cell,
            toCell: step(cell, dir, count), count: count, dir: dir)))
        else:
          actions.add(newJNull())
  for cell in 0 ..< Cells:
    if legal[MoveSlots + cell]:
      actions.add(actionOf(Move(kind: mkPlace, fromCell: -1, toCell: cell)))
    else:
      actions.add(newJNull())
  %*{"decision_id": id, "values": values, "actions": actions}

when isMainModule:
  let args = commandLineParams()
  if args.len notin 1 .. 2:
    quit("usage: focus-train-bridge MANIFEST [VARIANT]", 1)
  let variant = if args.len == 2: args[1] else: "standard"
  let manifest = parseFile(args[0])
  var variantConfig: JsonNode
  for entry in manifest["variants"]:
    if entry["id"].getStr() == variant:
      variantConfig = entry["game_config"]
  doAssert not variantConfig.isNil, "unknown variant: " & variant
  var game: Sim
  var client: LlmClient
  var id = 0
  while not stdin.endOfFile:
    let request = parseJson(stdin.readLine())
    var response: JsonNode
    case request["kind"].getStr()
    of "reset":
      doAssert request["players"].getInt() == Seats
      var config = defaultGameConfig()
      let runtimeConfig = copy(variantConfig)
      runtimeConfig["tokens"] = %*["t0", "t1"]
      runtimeConfig["seed"] = %seedOf(request["seed"].getStr())
      config.update($runtimeConfig)
      config = sampleEpisode(config)
      game = initSim(config)
      client = newScriptedClient(config)
      id = 0
      response = game.decision(id)
    of "encode":
      doAssert not game.done
      response = game.encoding(id)
    of "teacher":
      doAssert not game.done
      response = %*{"response": $actionOf(client.scriptedAction(game, game.turn).move)}
    of "step":
      doAssert not game.done and request["decision_id"].getInt() == id
      let action = parseJson(request["response"].getStr())
      let seat = game.turn
      let parsed = parseDecision(game, seat, action)
      doAssert parsed.move in game.legalMoves(seat)
      game.recordSay(seat, parsed.say)
      game.applyMove(seat, parsed.move)
      inc id
      var observation: JsonNode
      if game.done:
        let outcome = game.resultsJson()
        var scores = newJObject()
        for slot in 0 ..< Seats:
          scores[$slot] = outcome["scores"][slot]
        observation = %*{"kind": "terminal", "scores": scores}
      else:
        observation = game.decision(id)
      response = %*{"kind": "accepted", "action": action,
        "observation": observation}
    else:
      raise newException(ValueError, "unknown command: " & request["kind"].getStr())
    stdout.writeLine($response)
    stdout.flushFile()
