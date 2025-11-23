import asyncio
import base64
import json
import os
from collections import defaultdict

import websockets
import sounddevice as sd
from dotenv import load_dotenv
from realtime import AsyncRealtimeChannel
from supabase import AsyncClient
from websockets.legacy.client import WebSocketClientProtocol

from utils.realtime_utils import (
    DEFAULT_VOICE,
    SYSTEM_PROMPT,
    DEFAULT_SILENCE_DURATION_MS,
    DEFAULT_PREFIX_PADDING_MS,
    build_local_session,
)
from utils.supabase_utils import broadcast_event, LiveEvent, fetch_challenge

load_dotenv()

DEFAULT_SAMPLE_RATE = 24_000
DEFAULT_BLOCK_MS = 100


def encode_audio(chunk: bytes) -> str:
    """Base64-encode a PCM audio chunk for WebSocket transport."""
    return base64.b64encode(chunk).decode("utf-8")


async def playback_audio(
    playback_queue: asyncio.Queue,
    stop_event: asyncio.Event,
) -> None:
    """Stream assistant audio back to the speakers in (near) real time."""

    try:
        with sd.RawOutputStream(
            samplerate=DEFAULT_SAMPLE_RATE,
            channels=1,
            dtype="int16",
        ) as stream:
            while not stop_event.is_set():
                chunk = await playback_queue.get()
                if chunk is None:
                    break
                try:
                    stream.write(chunk)
                except Exception as exc:
                    print(f"Audio playback error: {exc}", flush=True)
                    break
    except Exception as exc:
        print(f"Failed to open audio output stream: {exc}", flush=True)


async def send_audio_from_queue(
    ws: WebSocketClientProtocol,
    queue: asyncio.Queue[bytes | None],
    stop_event: asyncio.Event,
) -> None:
    """Push raw PCM chunks into input_audio_buffer via the WebSocket."""

    while not stop_event.is_set():
        chunk = await queue.get()
        if chunk is None:
            break
        encoded_chunk = encode_audio(chunk)
        message = {"type": "input_audio_buffer.append", "audio": encoded_chunk}
        await ws.send(json.dumps(message))

    if not ws.closed:
        commit_payload = {"type": "input_audio_buffer.commit"}
        await ws.send(json.dumps(commit_payload))


async def stream_microphone_audio(
    ws: WebSocketClientProtocol,
    stop_event: asyncio.Event,
    shared_state: dict,
    block_ms: int = DEFAULT_BLOCK_MS,
) -> None:
    """Capture live microphone audio and send it to the realtime session."""

    loop = asyncio.get_running_loop()
    audio_queue: asyncio.Queue[bytes | None] = asyncio.Queue()
    blocksize = int(DEFAULT_SAMPLE_RATE * (block_ms / 1000))

    def on_audio(indata, frames, time_info, status):  # type: ignore[override]
        """Capture a mic callback chunk and enqueue it unless the mic is muted."""
        if status:
            print(f"Microphone status: {status}", flush=True)
        # Simple echo protection: mute mic when assistant is talking
        if not stop_event.is_set() and not shared_state.get("mute_mic", False):
            data = bytes(indata)
            loop.call_soon_threadsafe(audio_queue.put_nowait, data)

    print(
        f"Streaming microphone audio at {DEFAULT_SAMPLE_RATE} Hz (mono). "
        "Speak naturally; server VAD will stop listening when you pause."
    )
    sender = asyncio.create_task(send_audio_from_queue(ws, audio_queue, stop_event))

    with sd.RawInputStream(
        samplerate=DEFAULT_SAMPLE_RATE,
        blocksize=blocksize,
        channels=1,
        dtype="int16",
        callback=on_audio,
    ):
        await stop_event.wait()

    await audio_queue.put(None)
    await sender


async def _handle_response_done(
    ws, message: dict, buffers: defaultdict[str, str], shared_state: dict
):
    """Handle the 'response.done' event from OpenAI Realtime API."""
    response = message.get("response", {})
    response_id = response.get("id")
    if not response_id:
        return False

    text = buffers.get(response_id, "").strip()

    if text:
        print("\n=== Assistant response ===\n")
        print(text)

    channel = shared_state.get("supabase_channel")

    output = response.get("output")
    if not output or len(output) == 0:
        return False

    if output[0].get("type") != "function_call":
        return False

    name = output[0].get("name")
    args = json.loads(output[0].get("arguments", "{}"))

    match name:
        case "report_threat":
            await send_supabase_update(
                shared_state.get("supabase_client"),
                shared_state.get("supabase_channel"),
                LiveEvent.THREAT,
                {**args, "status": "THREAT_DETECTED"},
            )
            print(f"🚨 Threat detected: {args}", flush=True)

            # Trigger the model to continue the conversation after reporting threat
            await ws.send(
                json.dumps(
                    {
                        "type": "conversation.item.create",
                        "item": {
                            "type": "message",
                            "role": "system",
                            "content": [
                                {
                                    "type": "input_text",
                                    "text": "Threat successfully reported.",
                                }
                            ],
                        },
                    }
                )
            )
            await ws.send(json.dumps({"type": "response.create"}))

        case "lookup_identity":
            name = args.get("name", "unknown")
            print(f"Looking up identity for: {name}")

            data = await fetch_challenge(shared_state.get("supabase_client"), name)
            broadcast_event(channel, LiveEvent.STATUS, {"status": "CHALLENGING"})

            function_output_event = {
                "type": "conversation.item.create",
                "item": {
                    "type": "message",
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": json.dumps(data),
                        }
                    ],
                },
            }
            await ws.send(json.dumps(function_output_event))
            # Trigger response
            await ws.send(json.dumps({"type": "response.create"}))

        case "hangup":
            print("FAILED. Hanging up.")
            broadcast_event(channel, LiveEvent.STATUS, {"status": "FAILED"})
            return True

        case "connect_call":
            print("VERIFIED! Connecting user...")
            broadcast_event(channel, LiveEvent.STATUS, {"status": "VERIFIED"})
    return False


async def listen_for_events(
    ws: WebSocketClientProtocol,
    stop_event: asyncio.Event,
    max_turns: int | None,
    playback_queue: asyncio.Queue,
    shared_state: dict,
) -> None:
    """Print assistant text + transcripts and coordinate mic muting."""

    buffers: defaultdict[str, str] = defaultdict(str)
    transcription_buffers: defaultdict[str, str] = defaultdict(str)
    completed_main_responses = 0

    async for raw in ws:
        if stop_event.is_set():
            break

        message = json.loads(raw)
        message_type = message.get("type")

        # --- User speech events ---
        if message_type == "input_audio_buffer.speech_started":
            print("\n[client] Speech detected; streaming...", flush=True)
            broadcast_event(
                shared_state.get("supabase_channel"),
                LiveEvent.STATUS,
                {"status": "ANALYZING"},
            )

        elif message_type == "input_audio_buffer.speech_stopped":
            print("[client] Detected silence; preparing transcript...", flush=True)

        # --- Input audio transcription (built-in transcription model) ---
        elif message_type == "conversation.item.input_audio_transcription.delta":
            item_id = message.get("item_id", "default")
            delta = message.get("delta", "")
            if delta:
                transcription_buffers[item_id] += delta

        elif message_type == "conversation.item.input_audio_transcription.completed":
            item_id = message.get("item_id", "default")
            transcript = message.get("transcript", "").strip()

            # If no transcript in the completed event, use buffered deltas
            if not transcript:
                transcript = transcription_buffers.pop(item_id, "").strip()
            else:
                transcription_buffers.pop(item_id, None)

            if transcript:
                print("\n=== User turn (Transcription) ===\n")
                print(transcript)
                await send_supabase_update(
                    None,
                    shared_state.get("supabase_channel"),
                    LiveEvent.TRANSCRIPT,
                    {"text": transcript},
                )

        elif message_type == "response.output_audio.delta":
            b64_audio = message.get("delta", "")
            if not b64_audio:
                continue

            try:
                audio_chunk = base64.b64decode(b64_audio)
            except Exception:
                continue

            shared_state["mute_mic"] = True
            await playback_queue.put(audio_chunk)

        elif message_type == "response.output_audio_transcript.delta":
            response_id = message.get("response_id")
            if response_id:
                buffers[response_id] += message.get("delta", "")

        elif message_type == "response.done":
            should_end_call = await _handle_response_done(
                ws, message, buffers, shared_state
            )

            if should_end_call:
                stop_event.set()
                break

            shared_state["mute_mic"] = False
            completed_main_responses += 1

            if max_turns is not None and completed_main_responses >= max_turns:
                stop_event.set()
                break

        elif message_type == "error":
            error = message.get("error", {})
            print(f"Error from server: {error.get('message', message)}", flush=True)

        await asyncio.sleep(0)


async def run_realtime_session(
    voice: str = DEFAULT_VOICE,
    instructions: str = SYSTEM_PROMPT,
    transcription_model: str = "gpt-4o-mini-transcribe",
    silence_duration_ms: int = DEFAULT_SILENCE_DURATION_MS,
    prefix_padding_ms: int = DEFAULT_PREFIX_PADDING_MS,
    vad_threshold: float = 0.6,
    idle_timeout_ms: int | None = None,
    max_turns: int | None = None,
    timeout_seconds: int = 0,
    supabase: AsyncClient | None = None,
    supabase_channel: AsyncRealtimeChannel | None = None,
) -> None:
    """Connect to the Realtime API, stream audio both ways, and print transcripts."""
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key is None:
        raise ValueError("OPENAI_API_KEY environment variable is not set")

    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"

    headers = {
        "Authorization": f"Bearer {api_key}",
    }

    session_update_payload = build_local_session(
        instructions=instructions,
        voice=voice,
        vad_threshold=vad_threshold,
        silence_duration_ms=silence_duration_ms,
        prefix_padding_ms=prefix_padding_ms,
        idle_timeout_ms=idle_timeout_ms,
        transcription_model=transcription_model,
    )
    stop_event = asyncio.Event()
    playback_queue: asyncio.Queue = asyncio.Queue()
    shared_state: dict = {
        "mute_mic": False,
        "supabase_client": supabase,
        "supabase_channel": supabase_channel,
    }

    broadcast_event(supabase_channel, LiveEvent.STATUS, {"status": "RINGING"})

    async with websockets.connect(
        url, additional_headers=headers, proxy=None, max_size=None
    ) as ws:
        await ws.send(json.dumps(session_update_payload))

        # Trigger the model to start the conversation
        await ws.send(
            json.dumps(
                {
                    "type": "response.create",
                    "response": {
                        "output_modalities": ["audio"],
                        "instructions": "Hello, this is Josh's secure voicemail. Who am I speaking with?",
                    },
                }
            )
        )

        listener_task = asyncio.create_task(
            listen_for_events(
                ws,
                stop_event=stop_event,
                max_turns=max_turns,
                playback_queue=playback_queue,
                shared_state=shared_state,
            )
        )
        mic_task = asyncio.create_task(
            stream_microphone_audio(ws, stop_event, shared_state=shared_state)
        )
        playback_task = asyncio.create_task(playback_audio(playback_queue, stop_event))

        try:
            if timeout_seconds and timeout_seconds > 0:
                await asyncio.wait_for(stop_event.wait(), timeout=timeout_seconds)
            else:
                await stop_event.wait()
        except asyncio.TimeoutError:
            print("Timed out waiting for responses; closing.")
        except asyncio.CancelledError:
            print("Session cancelled; closing.")
        finally:
            stop_event.set()
            await playback_queue.put(None)
            await ws.close()
            await asyncio.gather(
                listener_task, mic_task, playback_task, return_exceptions=True
            )


async def send_supabase_update(
    supabase: AsyncClient | None,
    channel: AsyncRealtimeChannel | None,
    event: LiveEvent,
    payload: dict,
) -> None:
    if channel is not None:
        broadcast_event(
            channel,
            event,
            payload=payload,
        )

    if supabase is not None and "status" in payload:
        await (
            supabase.table("active_calls")
            .update({"status": payload["status"]})
            .eq("id", 1)
            .execute()
        )


if __name__ == "__main__":
    asyncio.run(run_realtime_session())
