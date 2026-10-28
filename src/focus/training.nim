## Private native evidence; the native request, parser and game rules remain unchanged.
import std/[json, options, os, strutils]
import bitworld/decision_trajectory
import curly, crunchy
import sim, prompts
export decision_trajectory

proc nativeScenarioFamily*(config: GameConfig): string =
  # Seed changes anonymous aliases and first mover, not the fixed opening board.
  # Group repeated physical openings together across wordings and alias seeds.
  let initial = initSim(config)
  let physical = %*{"board": initial.boardJson(), "first": initial.first,
    "maxPlies": config.maxPlies}
  "focus-physical-v1-" & sha256($physical).toHex.toLowerAscii()

proc initNativeTrajectory*(config: GameConfig): DecisionTrajectory =
  if getEnv(CogameSaveTrajectoryUriEnv).len == 0: return nil
  newDecisionTrajectory(getEnv("COWORLD_EPISODE_ID"), nativeScenarioFamily(config),
    "focus", getEnv("COWORLD_GAME_VERSION"), getEnv("COWORLD_SOURCE_REVISION"))

proc nativeAttempt*(policy: string, turn, seat, retry: int, body: string): DecisionAttempt =
  result = newDecisionAttempt($turn & "-" & $seat & "-attempt-" & $retry, policy, aoModel)
  result.request = parseJson(body)
  result.prompt = %*[{"role": "system", "content": result.request["system"]}]
  for message in result.request["messages"]: result.prompt.add(copy(message))
  result.decoder = newJObject()
  for key, value in result.request:
    if key notin ["model", "system", "messages", "anthropic_version"]:
      result.decoder[key] = copy(value)

proc receiveNativeResponse*(attempt: var DecisionAttempt, response: Response,
    transportError: string, latencyMs: int) =
  # Curly returns received, decompressed body bytes and parsed headers. Do not
  # manufacture a raw HTTP header block or claim unexposed transport facts.
  attempt.rawResponse = %response.body
  attempt.latencyMs = some(latencyMs.float)
  for (header, field) in [
      ("x-softmax-llm-call-id", "call"),
      ("x-coworld-checkpoint-sha256", "model"),
      ("x-coworld-tokenizer-sha256", "tokenizer"),
      ("x-coworld-chat-template-sha256", "template")]:
    let value = response.headers[header]
    if value.len > 0:
      case field
      of "call": attempt.platformCallId = some(value)
      of "model": attempt.modelIdentity = some(value)
      of "tokenizer": attempt.tokenizerIdentity = some(value)
      of "template": attempt.chatTemplateSha256 = some(value)
  if transportError.len > 0 or response.code < 200 or response.code >= 300: return
  let payload = parseJson(response.body)
  if payload.hasKey("model") and payload["model"].kind == JString:
    attempt.model = some(payload["model"].getStr())
  if payload.hasKey("stop_reason") and payload["stop_reason"].kind == JString:
    attempt.stopReason = some(payload["stop_reason"].getStr())
  let usage = payload{"usage"}
  if not usage.isNil and usage.kind == JObject:
    if usage.hasKey("input_tokens") and usage["input_tokens"].kind == JInt: attempt.inputTokens = some(usage["input_tokens"].getInt())
    if usage.hasKey("output_tokens") and usage["output_tokens"].kind == JInt: attempt.outputTokens = some(usage["output_tokens"].getInt())
  var text = ""
  for part in payload["content"]:
    if part{"type"}.getStr() == "text": text.add(part{"text"}.getStr())
  attempt.response = %text

proc recordAppliedDecision*(trajectory: DecisionTrajectory, selection: PromptSelection,
    ply, seat: int, policy: string, observation, action: JsonNode,
    fallback: bool, evidence: seq[DecisionAttempt]) =
  if trajectory.isNil: return
  var attempts = evidence
  var selected = none(string)
  var status = asAccepted
  var fallbackOrigin = none(string)
  if fallback:
    status = asFallback
    fallbackOrigin = some("engine-tactician-or-unattributed-external")
    for attempt in attempts.mitems: attempt.accepted = false
  elif attempts.len > 0:
    doAssert attempts[^1].parsedAction == action
    if attempts[^1].accepted: selected = some(attempts[^1].attemptId)
    else: status = asRejected
  if attempts.len == 0:
    var attempt = newDecisionAttempt($ply & "-" & $seat & "-unknown", policy, aoUnknown)
    attempt.parsedAction = action
    attempt.accepted = not fallback
    attempts.add(attempt)
    if not fallback: selected = some(attempt.attemptId)
  var view = copy(observation)
  view["prompt_selection"] = selection.selectionMetadata()
  view["prompt_attempts"] = newJArray()
  for attempt in attempts:
    if attempt.origin == aoModel:
      view["prompt_attempts"].add(%*{"attempt_id": attempt.attemptId,
        "prompt_template": selection.promptMetadata(attempt.request["system"].getStr(),
          attempt.request["messages"][0]["content"].getStr())})
  trajectory.recordDecision($ply & "-" & $seat, $seat, view,
    attempts, selected, action, status, fallbackOrigin = fallbackOrigin)

proc finishNativeTrajectory*(trajectory: DecisionTrajectory, game: Sim) =
  if trajectory.isNil: return
  let outcome = game.resultsJson()
  var scores = newJObject()
  for seat in 0 ..< Seats: scores[$seat] = outcome["scores"][seat]
  trajectory.finish(if game.reason in ["cap", "no-moves"]: esCompleted else: esTruncated,
    outcome, scores)
  trajectory.writeEventsToUri(getEnv(CogameSaveTrajectoryUriEnv))
