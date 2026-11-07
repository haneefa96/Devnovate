import os


if os.getenv("MUNSHI_RUN_HINDSIGHT_INTEGRATION") != "1":
    for name in (
    "GROQ_API_KEY",
    "HINDSIGHT_API_KEY",
    "HINDSIGHT_BASE_URL",
    "HINDSIGHT_LOCAL_URL",
    "BAND_API_KEY",
    "BAND_ROOM_ID",
    "BAND_AGENT_ID",
    "BAND_COLLECTOR_AGENT_ID",
    "BAND_COLLECTOR_API_KEY",
    "BAND_RISK_AGENT_ID",
    "BAND_RISK_API_KEY",
    ):
        os.environ[name] = ""
