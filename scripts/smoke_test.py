"""Smoke test: play 5 turns of Zork with the full turn graph."""
import logging
import sys
from zorkburr.app import build_turn_app
from zorkburr.config import GameConfig
from zorkburr.game.jericho_interface import JerichoInterface
from zorkburr.llm.client import create_llm_client
from zorkburr.state import S

logging.basicConfig(level=logging.INFO, format="%(name)s | %(message)s")
MAX_TURNS = 5


def main():
    config = GameConfig()
    if not config.openrouter_api_key or config.openrouter_api_key == "your-key-here":
        print("ERROR: Set OPENROUTER_API_KEY in .env")
        sys.exit(1)

    client = create_llm_client(config)

    with JerichoInterface(config.game_file) as jericho:
        jericho.start()
        print(f"\n{'='*60}")
        print("GAME START")
        print(f"{'='*60}")
        print(jericho.last_response)
        print(f"{'='*60}\n")

        app = build_turn_app(
            config=config, jericho=jericho, client=client,
            episode_id="smoke-test", tracker="local", persist=True,
        )
        print("NOTE: Burr state persisted to data/burr_state.db")

        turns_completed = 0
        while turns_completed < MAX_TURNS:
            action_obj, result, state = app.step()
            if action_obj.name == "execute_action":
                turns_completed += 1
                print(f"\n--- Turn {state[S.TURN_COUNT]} ---")
                print(f"Action: {state[S.ACTION_TO_TAKE]}")
                print(f"Response: {state[S.GAME_RESPONSE][:300]}")
                print(f"Score: {state[S.SCORE]} | Location: {state[S.LOCATION_NAME]}")
            if state[S.GAME_OVER]:
                print(f"\nGAME OVER: {state[S.GAME_OVER_REASON]}")
                break

        print(f"\n{'='*60}")
        print(f"Smoke test complete. Turns: {turns_completed}, Score: {state[S.SCORE]}")
        print(f"Burr tracking UI: run 'burr' to view at http://localhost:7241")
        print(f"{'='*60}")


if __name__ == "__main__":
    main()
