import json

SYSTEM_PROMPT = """
# Role & Objective        — who you are and what “success” means

- Your primary objective is to determine if the caller is a spam caller or not.
- You can be compared to a live firewall.
- If you determine the caller is legitimate, connect them to Josh.
- If you determine the caller is a scammer, hang up.

# Personality & Tone      — the voice and style to maintain

You are:

- Calm
- Professional
- Empathetic

# Language

- You communicate clearly and concisely in English.
- The conversation should only be in English.
- Do not respond in any other language, even if the user asks.
- Only respond to clear audio.

# Tools                   — names, usage rules, and preambles

You have access to 4 tools:

1. `connect_call`: Use this tool when you are confident the caller is legitimate.
2. `hangup`: Use this tool to hangup when you suspect scam.

# Instructions / Rules    — do’s, don’ts, and approach

- Always prioritize user safety and security.
- Do not share sensitive information with the caller.

# Conversation Flow       — states, goals, and transitions

- Start by saying "Hello, this is Josh's voice assistant. Who am I speaking with?"
- Listen for high-pressure scam tactics (bail money, gift cards, kidnapped).
- Listen for emotional distress (crying, shouting).
- Pay attention if you think the caller might be an impersonator (e.g., "Is this Josh?" or "Can you confirm your name?").
- Pay attention to any mention of a security question or code word.
- Watch for any signs of a scam, such as refusal to answer questions, background noise, or inconsistent information.

Greeting -> Listening -> Scam Detection -> Resolution

- If you detect a scam, immediately call the 'hangup' function. Do not say anything first.
- Otherwise call the `connect_call` function. Do not say anything first.
"""

DEFAULT_VOICE = "marin"
DEFAULT_PREFIX_PADDING_MS = 50
DEFAULT_BLOCK_MS = 100
DEFAULT_SILENCE_DURATION_MS = 800
DEFAULT_SAMPLE_RATE = 24_000


TOOLS = [
    {
        "type": "function",
        "name": "connect_call",
        "description": "Call this to connect the caller with Josh.",
        "parameters": {"type": "object", "properties": {}},
    },
    {
        "type": "function",
        "name": "hangup",
        "description": "Call this to hangup.",
        "parameters": {"type": "object", "properties": {}},
    },
]


def _build_session_config(
    instructions: str,
    vad_threshold: float,
    silence_duration_ms: int,
    prefix_padding_ms: int,
    idle_timeout_ms: int | None,
) -> tuple[dict[str, object], dict[str, object]]:
    turn_detection = {
        "type": "server_vad",
        "threshold": vad_threshold,
        "silence_duration_ms": silence_duration_ms,
        "prefix_padding_ms": prefix_padding_ms,
        "create_response": True,
        "interrupt_response": True,
    }

    if idle_timeout_ms is not None:
        turn_detection["idle_timeout_ms"] = idle_timeout_ms

    session = {
        "type": "realtime",
        "output_modalities": ["audio"],
        "instructions": instructions,
        "tools": TOOLS,
        "tool_choice": "auto",
    }

    return session, turn_detection


def build_twilio_session(
    instructions: str,
    voice: str,
    vad_threshold: float,
    silence_duration_ms: int,
    prefix_padding_ms: int,
    transcription_model: str,
    idle_timeout_ms: int | None,
) -> dict[str, object]:
    """Configure the Realtime session: audio in/out, server VAD, etc."""

    session, turn_detection = _build_session_config(
        instructions,
        vad_threshold,
        silence_duration_ms,
        prefix_padding_ms,
        idle_timeout_ms,
    )

    audio_config = {
        "input": {
            "format": {"type": "audio/pcmu"},
            "noise_reduction": {"type": "near_field"},
            "turn_detection": turn_detection,
            "transcription": {"model": transcription_model},
        },
        "output": {
            "format": {"type": "audio/pcmu"},
            "voice": voice,
        },
    }

    session["audio"] = audio_config

    # Optional: built-in transcription model for comparison

    return {
        "type": "session.update",
        "session": session,
    }


def build_local_session(
    instructions: str,
    voice: str,
    vad_threshold: float,
    silence_duration_ms: int,
    prefix_padding_ms: int,
    transcription_model: str,
    idle_timeout_ms: int | None,
) -> dict[str, object]:
    """Configure the Realtime session: audio in/out, server VAD, etc."""

    session, turn_detection = _build_session_config(
        instructions,
        vad_threshold,
        silence_duration_ms,
        prefix_padding_ms,
        idle_timeout_ms,
    )

    audio_config = {
        "input": {
            "format": {
                "type": "audio/pcm",
                "rate": DEFAULT_SAMPLE_RATE,
            },
            "noise_reduction": {"type": "near_field"},
            "turn_detection": turn_detection,
            "transcription": {"model": transcription_model},
        },
        "output": {
            "format": {
                "type": "audio/pcm",
                "rate": DEFAULT_SAMPLE_RATE,
            },
            "voice": voice,
        },
    }

    session["audio"] = audio_config

    return {
        "type": "session.update",
        "session": session,
    }


async def force_model_continuation(websocket, text: str):
    await websocket.send(
        json.dumps(
            {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": f"{text}",
                        }
                    ],
                },
            }
        )
    )
    await websocket.send(json.dumps({"type": "response.create"}))
