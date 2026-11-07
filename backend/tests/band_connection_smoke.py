"""Standalone Band SDK connection and ping/pong smoke test."""

from __future__ import annotations

import asyncio
import re
import sys
from pathlib import Path

from band import Agent
from band.core import AgentToolsProtocol, PlatformMessage, SimpleAdapter

CONFIG_PATH = Path(__file__).resolve().parents[1] / "agent_config.yaml"


class PingPongAdapter(SimpleAdapter[None]):
    """Reply only to room messages that contain the word ping."""

    async def on_message(
        self,
        msg: PlatformMessage,
        tools: AgentToolsProtocol,
        history: None,
        participants_msg: str | None,
        contacts_msg: str | None,
        *,
        is_session_bootstrap: bool,
        room_id: str,
    ) -> None:
        if not re.search(r"\bping\b", msg.content, flags=re.IGNORECASE):
            await tools.no_reply("Standalone smoke test handles ping only")
            return
        if not msg.sender_id:
            await tools.no_reply("Incoming message did not include a sender identity")
            return
        await tools.send_message("pong", mentions=[msg.sender_id])


async def run_agent() -> None:
    if not CONFIG_PATH.is_file():
        raise FileNotFoundError(
            f"Band credentials file not found at {CONFIG_PATH}. "
            "Create it using the existing registered agent credentials."
        )

    agent = Agent.from_config(
        "munshi",
        adapter=PingPongAdapter(),
        config_path=CONFIG_PATH,
    )
    print("Loaded credentials for Band agent 'munshi' (values hidden).")
    print("Starting Band. Mention the agent with 'ping' in a private room; press Ctrl+C to stop.")
    await agent.run()


if __name__ == "__main__":
    try:
        asyncio.run(run_agent())
    except KeyboardInterrupt:
        print("Band smoke test stopped.")
    except Exception as error:
        print(
            f"Band smoke test failed ({type(error).__name__}). "
            "Check the existing agent config, network access, and Band agent permissions.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
