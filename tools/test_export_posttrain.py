"""Complete native Focus exports joined to installed moves and resulting boards."""

import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORTER = Path(sys.argv[1]).resolve()
OUTPUT = Path(tempfile.mkdtemp(prefix="focus-source-export-")) / "games"
revision = subprocess.check_output(
    ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
).strip()
subprocess.run(
    [str(EXPORTER), str(OUTPUT), "10", "1", "standard"],
    cwd=ROOT,
    check=True,
    timeout=600,
)
manifest = json.loads((OUTPUT / "manifest.json").read_text())
assert manifest["source_revision"] == revision and len(manifest["runs"]) == 10
assert (
    not (OUTPUT / "train.jsonl").exists() and not (OUTPUT / "validation.jsonl").exists()
)
for name in ("manifest.json", "trajectories.jsonl", "execution.jsonl"):
    assert (OUTPUT / name).stat().st_mode & 0o777 == 0o600
episodes, decisions, executions = {}, {}, {}
for line in (OUTPUT / "trajectories.jsonl").read_text().splitlines():
    row = json.loads(line)
    assert row["source_revision"] == revision
    if row["event_type"] == "episode":
        episodes[row["episode_id"]] = row
    else:
        decisions.setdefault(row["episode_id"], []).append(row)
        (attempt,) = row["attempts"]
        assert (
            attempt["origin"] == "teacher" and attempt["policy"] == "scripted-baseline"
        )
        assert (
            attempt["request"] is None
            and attempt["platform_call_id"] is None
            and attempt["behavior_logprobs"] is None
        )
        assert attempt["accepted"] and row["action_status"] == "accepted"
        assert row["selected_attempt_id"] == attempt["attempt_id"]
        assert (
            row["executed_action"]
            == attempt["parsed_action"]
            == json.loads(attempt["response"])
        )
        metadata = row["observation"]["prompt_template"]
        assert (
            metadata["bank"] == "focus-rules-v1" and metadata["variant"] == "canonical"
        )
        for message in attempt["prompt"]:
            assert (
                metadata[message["role"] + "_sha256"].lower()
                == hashlib.sha256(message["content"].encode()).hexdigest()
            )
for line in (OUTPUT / "execution.jsonl").read_text().splitlines():
    row = json.loads(line)
    assert row["visibility"] == "private" and row["source_revision"] == revision
    executions.setdefault(row["episode_id"], []).append(row)
assert len(episodes) == 10 and set(episodes) == set(decisions) == set(executions)
for episode, outcome in episodes.items():
    rows, applied = decisions[episode], executions[episode]
    assert outcome["status"] == "completed" and outcome["outcome"]["reason"] in (
        "cap",
        "no-moves",
    )
    assert len(rows) == len(applied) == outcome["outcome"]["plies"] <= 120
    assert sum(row["terminal"] for row in rows) == 1 and rows[-1]["terminal"]
    previous = None
    for index, (row, execution) in enumerate(zip(rows, applied, strict=True)):
        view = dict(row["observation"])
        view.pop("prompt_template")
        assert row["decision_id"] == execution["decision_id"] == str(index)
        assert execution["turn"] == view["ply"] == index
        assert row["seat"] == str(execution["seat"]) == str(view["turn"])
        assert execution["event_end"] - execution["event_start"] == len(
            execution["events"]
        )
        if previous is not None:
            assert view == previous["resulting_state"]
            assert execution["event_start"] == previous["event_end"]
        previous = execution
        action = row["executed_action"]
        assert action == execution["installed_action"]
        (move,) = [
            event for event in execution["events"] if event["kind"] in ("move", "place")
        ]
        if move["kind"] == "place":
            assert action["place"] == chr(97 + move["to"] % 8) + str(
                move["to"] // 8 + 1
            )
        else:
            assert action["move"] == {
                "from": chr(97 + move["from"] % 8) + str(move["from"] // 8 + 1),
                "count": move["count"],
                "dir": move["dir"],
            }
        speech = [
            event["text"] for event in execution["events"] if event["kind"] == "say"
        ]
        assert action["say"] == (speech[0] if speech else "")
        assert execution["resulting_state"]["ply"] == index + 1
    assert previous["resulting_state"]["gameDone"]
    for seat in range(2):
        assert (
            outcome["participant_outcomes"][str(seat)]["score"]
            == outcome["outcome"]["scores"][seat]
        )
assert {row["seed_family"] for row in episodes.values()} == {
    f"focus-{seed}" for seed in range(1, 11)
}
print(
    "10 complete source games; exact messages, installed moves, board continuity and outcomes PASS",
    OUTPUT,
    flush=True,
)
