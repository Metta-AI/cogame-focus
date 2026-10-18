"""Complete published Focus games through original and full text bridges."""

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BRIDGE, ORIGINAL = (Path(value).resolve() for value in sys.argv[1:3])
WORDINGS = (
    "canonical",
    "plain",
    "numbered",
    "questions",
    "reordered",
    "heldout-briefing",
    "heldout-reference",
)


def play(seed, wording="canonical", prompt_seed=0, original=False, speech=False):
    command = [
        str(ORIGINAL if original else BRIDGE),
        str(ROOT / "coworld_manifest_template.json"),
        "standard",
    ]
    if not original:
        command.append("text")
    with subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True
    ) as process:
        assert process.stdin is not None and process.stdout is not None

        def request(value):
            process.stdin.write(json.dumps(value) + "\n")
            process.stdin.flush()
            return json.loads(process.stdout.readline())

        observation = request(
            {
                "kind": "reset",
                "players": 2,
                "seed": str(seed),
                "promptVariant": wording,
                "promptSeed": prompt_seed,
                "split": "test",
            }
        )
        trace, systems = [], {}
        drops = 0
        while observation["kind"] == "decision":
            index, seat = observation["decision_id"], observation["seat"]
            assert index == len(trace)
            view, messages = observation["semantic_view"], observation["messages"]
            systems.setdefault(seat, messages[0]["content"])
            assert systems[seat] == messages[0]["content"]
            if not original:
                metadata = view.pop("prompt_template")
                assert metadata["bank"] == "focus-rules-v1"
                assert metadata["variant"] == (
                    WORDINGS[prompt_seed] if wording == "mixed" else wording
                )
                for message in messages:
                    assert (
                        metadata[message["role"] + "_sha256"].lower()
                        == hashlib.sha256(message["content"].encode()).hexdigest()
                    )
            teacher = json.loads(request({"kind": "teacher"})["response"])
            if not original:
                if speech:
                    teacher["say"] = "  PUBLIC-TALK-" + "x" * 200 + "  "
                    if "move" in teacher:
                        teacher["move"]["count"] = str(teacher["move"]["count"])
                        teacher["move"]["direction"] = (
                            teacher["move"].pop("dir").lower()
                        )
                    else:
                        teacher["place"] = {"to": teacher["place"]}
                else:
                    teacher["say"] = ""
            if "place" in teacher:
                drops += 1
            result = request(
                {"kind": "step", "decision_id": index, "response": json.dumps(teacher)}
            )
            assert result["kind"] == "accepted"
            action = result["action"]
            if speech:
                assert (
                    action["say"].startswith("PUBLIC-TALK-")
                    and len(action["say"].encode()) <= 160
                )
                if "move" in action:
                    assert isinstance(action["move"]["count"], int) and action["move"][
                        "dir"
                    ] in ("N", "S", "E", "W")
                else:
                    assert isinstance(action["place"], str)
            trace.append((view, messages[1]["content"]))
            observation = result["observation"]
        assert 1 <= len(trace) <= 120 and sum(observation["scores"].values()) == 1
        process.stdin.close()
        assert process.wait(timeout=5) == 0
        return trace, observation, systems, drops


for seed in (17, 946001):
    baseline = play(seed, original=True)
    distinct = []
    for wording, prompt_seed in [(wording, 0) for wording in WORDINGS] + [
        ("mixed", i) for i in range(5)
    ]:
        result = play(seed, wording, prompt_seed)
        assert result[:2] == baseline[:2]
        if wording == "canonical":
            assert result[2] == baseline[2]
        if wording == "mixed":
            assert result[2] == distinct[prompt_seed]
        else:
            distinct.append(result[2])
    assert all(len({systems[seat] for systems in distinct}) == 7 for seat in range(2))
    print(
        seed, "12 complete text games and original numeric comparison PASS", flush=True
    )
spoken = play(17, speech=True)
assert spoken[3] > 0
print(
    "25 complete text games; two original games; speech and move/drop normalization PASS",
    flush=True,
)
for wording in WORDINGS[-2:]:
    result = subprocess.run(
        [str(BRIDGE), str(ROOT / "coworld_manifest_template.json"), "standard", "text"],
        input=json.dumps(
            {
                "kind": "reset",
                "players": 2,
                "seed": "17",
                "promptVariant": wording,
                "split": "train",
            }
        )
        + "\n",
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert (
        result.returncode != 0
        and "held-out wording cannot be used for training" in result.stderr
    )
print("Held-out training gate PASS", flush=True)
