"""Exercise Focus through Metta's numeric decision protocol."""

import json
import sys
import time
from pathlib import Path

from metta_training.decision_environment import DecisionEncoding
from metta_training.game import Terminal
from metta_training.session import GameBridge


BRIDGE = Path(sys.argv[1]).resolve()
MANIFEST = Path(__file__).resolve().parents[1] / "coworld_manifest_template.json"

for seed in ("test-1", "test-2"):
    start = time.monotonic()
    with GameBridge([str(BRIDGE), str(MANIFEST), "standard"]) as bridge:
        observation = bridge.reset(seed, 2)
        decisions = 0
        while not isinstance(observation, Terminal):
            encoding = DecisionEncoding.model_validate_json(bridge.request({"kind": "encode"}))
            assert len(encoding.values) == 331
            assert len(encoding.actions) == 1344
            action = json.loads(bridge.teacher())
            assert encoding.action_for(encoding.indices_for(action)) == action
            observation = bridge.step(observation.decision_id, json.dumps(action)).observation
            decisions += 1
        assert 1 <= decisions <= 120
        assert sum(observation.scores.values()) == 1
        print(seed, decisions, observation.scores, f"{time.monotonic() - start:.2f}s")
