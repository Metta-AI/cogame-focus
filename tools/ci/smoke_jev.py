"""Run a local Focus Jev container against the scripted player and mock SystemOne."""

import json
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


class MockSystemOne(BaseHTTPRequestHandler):
    choices: list[str] = []
    headers_seen: list[tuple[str | None, str | None]] = []

    def do_POST(self) -> None:
        assert self.path == "/v1/systemone"
        request = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        observation = json.loads(request["state"].split("Your observation:\n", 1)[1])
        criteria = request["questions"]["decision"]["criteria"]
        assert observation["game"] == "focus"
        assert "policyNames" not in observation
        assert "rules" in observation
        assert list(criteria) == [move for move in observation["legalMoves"]]
        choice = next(iter(criteria))
        self.choices.append(choice)
        self.headers_seen.append((self.headers.get("authorization"),
                                  self.headers.get("x-coworld-player-slot")))
        reply = {
            "model": "mock-jev",
            "answers": {"decision": {
                "type": "choice", "confidence": 1.0,
                "probabilities": {move: float(move == choice) for move in criteria},
            }},
            "usage": {"input_tokens": 1, "output_tokens": 1},
        }
        data = json.dumps(reply).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, format: str, *args: object) -> None:
        pass


def free_port() -> int:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        return listener.getsockname()[1]


def main() -> None:
    output = Path(sys.argv[1]).resolve()
    output.mkdir(parents=True, exist_ok=True)
    image = sys.argv[2] if len(sys.argv) > 2 else "focus-jev-25001:local"
    mock = ThreadingHTTPServer(("0.0.0.0", 0), MockSystemOne)
    thread = threading.Thread(target=mock.serve_forever, daemon=True)
    thread.start()
    try:
        for jev_slot in (0, 1):
            MockSystemOne.choices = []
            MockSystemOne.headers_seen = []
            port = free_port()
            episode = output / f"seat-{jev_slot}"
            episode.mkdir(exist_ok=True)
            config = {
                "tokens": ["focus-a", "focus-b"],
                "players": [{"name": "Jev" if seat == jev_slot else "Scripted"}
                            for seat in range(2)],
                "seed": jev_slot,
                "maxPlies": 6,
                "turnDelayMs": 0,
                "llmTimeoutSeconds": 5,
                "player_connect_timeout_seconds": 10.0,
            }
            game_name = f"focus-jev-smoke-{jev_slot}"
            game_log = (episode / "game.log").open("w")
            game = subprocess.Popen([
                "docker", "run", "--rm", "--platform=linux/amd64",
                "--name", game_name, "-p", f"{port}:8080",
                "-v", f"{episode}:/out", image, "/bin/focus",
                "--config:" + json.dumps(config, separators=(",", ":")),
                "--results-uri:file:///out/results.json",
                "--save-replay-uri:file:///out/replay.json",
            ], stdout=game_log, stderr=subprocess.STDOUT)
            players = []
            try:
                for _ in range(100):
                    if game.poll() is not None:
                        break
                    if subprocess.run([
                        "curl", "-fsS", "--max-time", "1",
                        f"http://127.0.0.1:{port}/healthz",
                    ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                        break
                    time.sleep(0.1)
                assert game.poll() is None, (episode / "game.log").read_text()
                for seat in range(2):
                    env = ["-e", f"COWORLD_PLAYER_WS_URL=ws://host.docker.internal:{port}/player?slot={seat}&token=focus-{'a' if seat == 0 else 'b'}"]
                    if seat == jev_slot:
                        env += ["-e", "PLAYER_JEV=1"]
                        if jev_slot == 0:
                            env += ["-e", f"METTA_CAPTURE_URL=http://host.docker.internal:{mock.server_port}", "-e", "METTA_CAPTURE_KEY=mock"]
                        else:
                            env += ["-e", f"AWS_ENDPOINT_URL_BEDROCK_RUNTIME=http://host.docker.internal:{mock.server_port}"]
                    else:
                        env += ["-e", "PLAYER_SCRIPTED=1"]
                    log = (episode / f"player-{seat}.log").open("w")
                    player = subprocess.Popen(["docker", "run", "--rm", "--platform=linux/amd64", *env, image, "/bin/focus-player"], stdout=log, stderr=subprocess.STDOUT)
                    players.append((player, log))
                assert game.wait(timeout=50) == 0, (episode / "game.log").read_text()
                for player, _ in players:
                    assert player.wait(timeout=10) == 0
                replay = json.loads((episode / "replay.json").read_text())
                results = json.loads((episode / "results.json").read_text())
                log = (episode / "game.log").read_text()
                assert results["plies"] == 6
                assert len(MockSystemOne.choices) == 3
                if jev_slot == 0:
                    assert MockSystemOne.headers_seen == [("Bearer mock", None)] * 3
                else:
                    assert MockSystemOne.headers_seen == [(None, "1")] * 3
                assert log.count(f"focus: external accepted seat {jev_slot}") == 3
                assert "external fallback" not in log
                assert sum(event["kind"] == "move" for event in replay["events"]) == 6
                for choice in MockSystemOne.choices:
                    assert choice in log
                print(f"seat {jev_slot}: {results['plies']} plies, 3 accepted Jev moves, 0 fallback")
            finally:
                subprocess.run(["docker", "stop", game_name], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                for player, log in players:
                    if player.poll() is None:
                        player.terminate()
                        player.wait(timeout=5)
                    log.close()
                game_log.close()
    finally:
        mock.shutdown()
        mock.server_close()


if __name__ == "__main__":
    main()
