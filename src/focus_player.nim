## Focus player: prompt, scripted baseline, or external Jev policy.
##
## PLAYER_JEV=1 chooses from the game's legal actions in this container.
##
## PLAYER_SCRIPTED=1 registers the seat as the built-in minimax baseline
## instead: the server plays it deterministically, no LLM.
##
## To field your own policy, reuse this image and set PLAYER_PROMPT:
##   coworld upload-policy <focus-image> --name my-focus \
##     --run /bin/focus-player --secret-env PLAYER_PROMPT="<your strategy>"

import
  std/[json, options, os, strutils],
  focus/jev_policy,
  whisky

const DefaultPrompt = """
Play sound Focus. Take control of enemy stacks by landing on them, and
prefer captures that strip enemy pieces off the bottom of tall stacks.
Keep several stacks under your control so you always have moves; never
leave your last stack where it can be buried. Bank reserve pieces from
your own overflow and drop them to seize key stacks late. Use the table
talk to needle your opponent, but never explain your real plan.
"""

when isMainModule:
  let url = getEnv("COWORLD_PLAYER_WS_URL")
  if url.len == 0:
    quit("COWORLD_PLAYER_WS_URL is not set", 1)
  let jev = getEnv("PLAYER_JEV").strip() in ["1", "true", "yes"]
  var prompt = getEnv("PLAYER_PROMPT")
  if prompt.len == 0 and not jev:
    prompt = DefaultPrompt
  let scripted = getEnv("PLAYER_SCRIPTED").strip() in ["1", "true", "yes"]
  if jev and scripted:
    quit("PLAYER_JEV and PLAYER_SCRIPTED cannot both be set", 1)

  proc promptFrame(): string =
    $ %*{"type": "prompt", "prompt": prompt, "scripted": scripted}

  echo "focus player: connecting to game"
  let socket = newWebSocket(url)
  if jev:
    socket.send($ %*{"type": "register", "control": "external"})
    echo "focus player: Jev external policy registered"
  else:
    socket.send(promptFrame())
    echo "focus player: prompt delivered (", prompt.len, " chars",
      (if scripted: ", scripted" else: ""), ")"

  while true:
    let received = socket.receiveMessage()
    if received.isNone:
      echo "focus player: connection closed, exiting"
      break
    let message = received.get()
    if message.kind != TextMessage:
      continue
    try:
      let payload = parseJson(message.data)
      case payload{"type"}.getStr()
      of "welcome":
        echo "focus player: seated at slot ",
          payload{"slot"}.getInt(), " as ", payload{"name"}.getStr()
        ## Re-deliver the prompt after the welcome, in case the first send
        ## raced the server's slot registration.
        if jev:
          socket.send($ %*{"type": "register", "control": "external"})
        else:
          socket.send(promptFrame())
      of "observation":
        if jev:
          let move = chooseMove(payload["observation"], prompt)
          socket.send($ %*{
            "type": "action", "id": payload["id"],
            "move": move, "say": ""})
      of "final":
        echo "focus player: final scores ", payload{"scores"}
        break
      else:
        discard
    except CatchableError as error:
      echo "focus player: ignoring bad frame: ", error.msg
  socket.close()
