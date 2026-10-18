"""Published Focus episodes with real players and a closed inference endpoint."""

import argparse
import hashlib
import json
import os
import socket
import subprocess
import time
from pathlib import Path


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("game", type=Path)
    parser.add_argument("player", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "coworld_manifest_template.json").read_text())
    variants = {entry["id"]: entry["game_config"] for entry in manifest["variants"]}
    cases = [(name, "canonical") for name in variants]
    cases += [
        ("standard", wording)
        for wording in (
            "plain",
            "numbered",
            "questions",
            "reordered",
            "heldout-briefing",
            "heldout-reference",
            "mixed",
        )
    ]
    if args.smoke:
        cases = [("standard", "canonical")]
    args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
    for variant, wording in cases:
        work = args.output / f"{variant}-{wording}"
        work.mkdir(mode=0o700)
        config = dict(variants[variant])
        seats = config["num_agents"]
        config.update(
            seed=7,
            promptVariant=wording,
            promptSeed=4,
            tokens=[f"t{seat}" for seat in range(seats)],
            players=[{"name": f"policy-{seat}"} for seat in range(seats)],
        )
        (work / "config.json").write_text(json.dumps(config))
        closed_endpoint = socket.socket()
        closed_endpoint.bind(("127.0.0.1", 0))
        closed_port = closed_endpoint.getsockname()[1]
        port = free_port()
        env = os.environ.copy()
        for key in (
            "ANTHROPIC_API_KEY",
            "ANTHROPIC_API_KEY_URI",
            "AWS_BEARER_TOKEN_BEDROCK",
            "AWS_ENDPOINT_URL_BEDROCK_RUNTIME",
            "PLAYER_SCRIPTED",
        ):
            env.pop(key, None)
        env.update(
            COGAME_HOST="127.0.0.1",
            COGAME_PORT=str(port),
            COGAME_CONFIG_URI=(work / "config.json").as_uri(),
            COGAME_RESULTS_URI=(work / "results.json").as_uri(),
            COGAME_SAVE_REPLAY_URI=(work / "episode.replay").as_uri(),
            COWORLD_LLM_ENDPOINT=f"http://127.0.0.1:{closed_port}",
            FOCUS_HOST_TRACE_PATH=str(work / "host.jsonl"),
            FOCUS_ATTEMPT_TRACE_DIR=str(work / "attempts"),
            FOCUS_SOURCE_REVISION="uncommitted-focus-validation",
        )
        processes, logs = [], []
        try:
            log = (work / "game.log").open("w")
            logs.append(log)
            game = subprocess.Popen(
                [str(args.game)],
                cwd=root,
                env=env,
                stdout=log,
                stderr=subprocess.STDOUT,
            )
            processes.append(game)
            for _ in range(200):
                assert game.poll() is None, work
                with socket.socket() as probe:
                    ready = probe.connect_ex(("127.0.0.1", port)) == 0
                if ready:
                    break
                time.sleep(0.05)
            else:
                raise RuntimeError(f"host did not start: {work}")
            for seat in range(seats):
                player_env = dict(
                    env,
                    COWORLD_PLAYER_WS_URL=f"ws://127.0.0.1:{port}/player?slot={seat}&token=t{seat}",
                    PLAYER_PROMPT=(
                        f"PRIVATE-STRATEGY-{seat}: Cooperate using only the information available to your role."
                    ),
                )
                log = (work / f"player-{seat}.log").open("w")
                logs.append(log)
                processes.append(
                    subprocess.Popen(
                        [str(args.player)],
                        cwd=root,
                        env=player_env,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                    )
                )
            assert game.wait(timeout=1200 + 30) == 0
            for player in processes[1:]:
                assert player.wait(timeout=15) == 0
            results = json.loads((work / "results.json").read_text())
            assert results["reason"] in ("cap", "no-moves")
            assert 1 <= results["plies"] <= config["maxPlies"] == 120
            records = [
                json.loads(line)
                for line in (work / "host.jsonl").read_text().splitlines()
            ]
            assert records[0]["event_type"] == "host_started"
            assert (
                records[-1]["event_type"] == "host_finished"
                and records[-1]["results"] == results
            )
            decisions = [row for row in records if row["event_type"] == "host_decision"]
            assert len(decisions) == results["plies"]
            starts, finishes = {}, {}
            for path in (work / "attempts").glob("*.jsonl"):
                assert path.stat().st_mode & 0o777 == 0o600
                start, finish = map(json.loads, path.read_text().splitlines())
                assert start["attempt_id"] == finish["attempt_id"]
                starts[start["attempt_id"]] = start
                finishes[finish["attempt_id"]] = finish
            assert len(starts) == 2 * len(decisions) and set(starts) == set(finishes)
            assert {
                identity for row in decisions for identity in row["attempt_ids"]
            } == set(starts)
            replay = json.loads((work / "episode.replay").read_text())
            assert replay["results"] == results
            for index, row in enumerate(decisions):
                seat = row["seat"]
                assert row["turn"] == index and row["observation"]["ply"] == index
                assert seat == row["observation"]["turn"]
                assert row["resulting_state"]["ply"] == index + 1
                assert (
                    row["policy_origin"] == "scripted-fallback"
                    and row["selected_attempt_id"] is None
                )
                assert len(row["attempt_ids"]) == 2
                for identity in row["attempt_ids"]:
                    start, finish = starts[identity], finishes[identity]
                    assert finish["failure"] and not finish["selected"]
                    assert (
                        finish["raw_response"] == "" and finish["parsed_action"] is None
                    )
                    assert (
                        finish["normalized_action"] is None
                        and finish["status_code"] == 0
                    )
                    assert (
                        finish["platform_call_id"] is None
                        and finish["behavior_logprobs"] is None
                    )
                    system, user = [message["content"] for message in start["prompt"]]
                    assert system == row["prompt"][0]["content"] and user.startswith(
                        row["prompt"][1]["content"]
                    )
                    assert f"PRIVATE-STRATEGY-{seat}" in user
                    assert f"PRIVATE-STRATEGY-{1 - seat}" not in user
                    body = start["request"]["body"]
                    assert (
                        body["system"] == system
                        and body["messages"] == start["prompt"][1:]
                    )
                    assert body["model"] == start["request"]["model"]
                    metadata = start["prompt_template"]
                    assert metadata["bank"] == "focus-rules-v1"
                    assert metadata["variant"] == (
                        "reordered" if wording == "mixed" else wording
                    )
                    for role, text in (("system", system), ("user", user)):
                        assert (
                            metadata[role + "_sha256"].lower()
                            == hashlib.sha256(text.encode()).hexdigest()
                        )
                assert (
                    row["events"]
                    == replay["events"][row["event_start"] : row["event_end"]]
                )
                (move,) = [
                    event
                    for event in row["events"]
                    if event["kind"] in ("move", "place")
                ]
                action = row["executed_action"]
                destination = chr(97 + move["to"] % 8) + str(move["to"] // 8 + 1)
                if move["kind"] == "place":
                    assert action["place"] == destination
                else:
                    assert action["move"] == {
                        "from": chr(97 + move["from"] % 8) + str(move["from"] // 8 + 1),
                        "count": move["count"],
                        "dir": move["dir"],
                    }
                speech = [
                    event["text"] for event in row["events"] if event["kind"] == "say"
                ]
                assert action["say"] == (speech[0] if speech else "")
                assert action == row["proposal"]
            assert (
                sum(row["terminal"] for row in decisions) == 1
                and decisions[-1]["terminal"]
            )
            public = (work / "episode.replay").read_text()
            assert "PRIVATE-STRATEGY-" not in public and "prompt_template" not in public
            assert (work / "host.jsonl").stat().st_mode & 0o777 == 0o600
            print(
                work.name,
                len(decisions),
                "plies;",
                len(starts),
                "actual failed requests; two real players PASS",
                flush=True,
            )
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
                    process.wait(timeout=10)
            for log in logs:
                log.close()
            closed_endpoint.close()


if __name__ == "__main__":
    main()
