"""Run the agent: python -m tvagent.app  (open src/tvagent/web/index.html in a browser)."""

from tvagent.config import build_orchestrator


def main() -> None:
    orch = build_orchestrator()
    print("Agent up. Open src/tvagent/web/index.html. Say the wake word.")
    while True:
        turn = orch.run_once()
        print(f"[{turn.person_id}] {turn.said} -> {turn.replied}")


if __name__ == "__main__":
    main()
