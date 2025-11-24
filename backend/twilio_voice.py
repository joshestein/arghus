import asyncio
import json
import os
from contextlib import asynccontextmanager

import ngrok
import uvicorn
import websockets
from dotenv import load_dotenv
from fastapi import FastAPI, Request, WebSocket
from fastapi.responses import HTMLResponse
from fastapi.websockets import WebSocketDisconnect
from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Connect, Stream
from websockets import ClientConnection

from openai_cookbook import (
    DEFAULT_VOICE,
    SYSTEM_PROMPT,
    DEFAULT_SILENCE_DURATION_MS,
    DEFAULT_PREFIX_PADDING_MS,
)
from utils.realtime_utils import build_twilio_session, force_model_continuation
from utils.supabase_utils import (
    create_async_supabase_client,
    broadcast_event,
    REALTIME_CHANNEL_NAME,
    LiveEvent,
    CallStatus,
    fetch_challenge,
)

load_dotenv()
TWILIO_API_SID = os.getenv("TWILIO_API_SID")
TWILIO_SECRET_KEY = os.getenv("TWILIO_SECRET_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_NUMBER_SID = os.getenv("TWILIO_NUMBER_SID")
USER_REAL_PHONE = os.getenv("USER_REAL_PHONE")
client = Client(TWILIO_API_SID, TWILIO_SECRET_KEY, TWILIO_ACCOUNT_SID)

NGROK_AUTH_TOKEN = os.getenv("NGROK_AUTH_TOKEN")
NGROK_DOMAIN = os.getenv("NGROK_DOMAIN")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

PORT = int(os.getenv("PORT", "8080"))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ENVIRONMENT != "production":
        print("Setting up ngrok tunnel...")
        listener = await ngrok.forward(
            addr=PORT,
            proto="http",
            authtoken=NGROK_AUTH_TOKEN,
            domain=NGROK_DOMAIN,
        )
        print(listener.url())
        twilio_phone = client.incoming_phone_numbers(TWILIO_NUMBER_SID).update(
            voice_url=listener.url() + "/voice"
        )
        print("Twilio voice URL: ", twilio_phone.voice_url)

        try:
            yield
        except asyncio.CancelledError:
            print("Lifespan cancelled")
        except KeyboardInterrupt:
            print("Lifespan interrupted by keyboard")
        finally:
            print("Closing ngrok tunnel...")
            ngrok.disconnect()
    else:
        yield


app = FastAPI(lifespan=lifespan)


@app.get("/")
async def root():
    return {"message": "Hello World"}


@app.api_route("/voice", methods=["GET", "POST"])
def voice(request: Request):
    """HTTP endpoint that returns TwiML to connect caller to WebSocket stream."""
    response = VoiceResponse()

    # Connect directly to the WebSocket stream (no greeting message)
    connect = Connect()
    stream = Stream(url=f"wss://{request.url.hostname}/audio-stream")
    connect.append(stream)
    response.append(connect)

    return HTMLResponse(content=str(response), media_type="application/xml")


async def send_to_openai(openai_ws, base64_audio: str) -> None:
    """Send base64-encoded audio directly to OpenAI Realtime API."""
    message = {"type": "input_audio_buffer.append", "audio": base64_audio}
    await openai_ws.send(json.dumps(message))


async def _receive_twilio_stream(
    twilio_ws, openai_ws: ClientConnection, channel, shared_state: dict
):
    """Receive audio from Twilio and forward to OpenAI Realtime API."""
    try:
        async for message in twilio_ws.iter_text():
            data = json.loads(message)
            match data["event"]:
                case "connected":
                    print("Connected to Twilio media stream")
                case "start":
                    shared_state["stream_sid"] = data["start"]["streamSid"]
                    shared_state["call_sid"] = data["start"]["callSid"]
                    print(
                        "Twilio stream started:",
                        shared_state.get("stream_sid"),
                        shared_state.get("call_sid"),
                    )
                    broadcast_event(
                        channel, LiveEvent.STATE, {"status": CallStatus.ANALYZING}
                    )
                case "media":
                    # Forward to OpenAI
                    base64_audio = data["media"]["payload"]
                    await send_to_openai(openai_ws, base64_audio)
                case "stop":
                    print("Twilio stream has stopped")
                    # broadcast_event(
                    #     channel,
                    #     LiveEvent.STATE,
                    #     {"status": "COMPLETED"},
                    # )
    except WebSocketDisconnect:
        print("Twilio webSocket disconnected")
    finally:
        await openai_ws.close()


async def _handle_response_done(
    ws, openai_response: dict, buffers: dict, channel, shared_state: dict
):
    """Handle the 'response.done' event from OpenAI Realtime API.

    :return True if the ws connection should be closed, False otherwise.
    """
    response = openai_response.get("response", {})
    response_id = response.get("id")
    if not response_id:
        return False

    text = buffers.get(response_id, "").strip()

    if text:
        print("\n=== assistant response ===\n")
        print(text)

    output = response.get("output")
    if not output or len(output) == 0:
        return False

    name = output[0].get("name")
    args = json.loads(output[0].get("arguments", "{}"))

    match name:
        case "report_threat":
            broadcast_event(
                channel,
                LiveEvent.STATE,
                {"status": CallStatus.THREAT_DETECTED, "data": {**args}},
            )
            shared_state["name"] = args.get("name")
            shared_state["confidence"] = args.get("confidence")

            print(f"🚨 Threat detected: {args}", flush=True)
            await force_model_continuation(ws, "Threat successfully reported.")

        case "lookup_identity":
            name = args.get("name", "unknown")
            shared_state["name"] = name
            print(f"Looking up identity for: {name}")

            data = await fetch_challenge(shared_state.get("supabase_client"), name)
            shared_state["question"] = data.get("question")

            broadcast_event(
                channel,
                LiveEvent.STATE,
                {
                    "status": CallStatus.CHALLENGING,
                    "data": {
                        "name": name,
                        "confidence": shared_state.get("confidence"),
                        "question": data.get("question"),
                    },
                },
            )
            await force_model_continuation(ws, json.dumps(data))

        case "hangup":
            print("FAILED. Hanging up.")
            broadcast_event(
                channel,
                LiveEvent.STATE,
                {
                    "status": CallStatus.FAILED,
                    "data": {"name": shared_state.get("name")},
                },
            )
            call_sid = shared_state.get("call_sid")
            if call_sid:
                twiml_patch = f"""<Response>
                   <Say>Verification failed. Goodbye.</Say>
               </Response>"""
                client.calls(call_sid).update(twiml=twiml_patch)
            return True

        case "connect_call":
            print("VERIFIED! Connecting user...")
            broadcast_event(
                channel,
                LiveEvent.STATE,
                {
                    "status": CallStatus.VERIFIED,
                    "data": {"name": shared_state.get("name")},
                },
            )
            call_sid = shared_state.get("call_sid")
            if call_sid:
                twiml_patch = f"""<Response>
                   <Say>Identity verified. Connecting you now.</Say>
                   <Dial>{USER_REAL_PHONE}</Dial>
               </Response>"""

                try:
                    client.calls(call_sid).update(twiml=twiml_patch)
                except TwilioRestException as err:
                    print(f"Error updating call TwiML: {err}", flush=True)

    return False


async def _send_ai_response(
    twilio_ws, openai_ws: ClientConnection, channel, shared_state: dict
):
    buffers: dict[str, str] = {}
    transcription_buffers: dict[str, str] = {}
    try:
        async for raw_message in openai_ws:
            stream_sid = shared_state.get("stream_sid")
            # Don't process messages until we have a stream_sid
            if not stream_sid:
                continue

            openai_response = json.loads(raw_message)
            openai_message_type = openai_response.get("type")

            if openai_message_type == "input_audio_buffer.speech_started":
                print("\n[client] Speech detected; streaming...", flush=True)
                await twilio_ws.send_json({"event": "clear", "streamSid": stream_sid})

            elif openai_message_type == "input_audio_buffer.speech_stopped":
                print(
                    "[client] Detected silence; preparing transcript...",
                    flush=True,
                )

            elif (
                openai_message_type
                == "conversation.item.input_audio_transcription.completed"
            ):
                item_id = openai_response.get("item_id", "default")
                transcript = openai_response.get("transcript", "").strip()

                # If no transcript in the completed event, use buffered deltas
                if not transcript:
                    transcript = transcription_buffers.pop(item_id, "").strip()
                else:
                    transcription_buffers.pop(item_id, None)

                if transcript:
                    print("\n=== User turn (Transcription) ===\n")
                    print(transcript)
                    broadcast_event(channel, LiveEvent.TRANSCRIPT, {"text": transcript})

            elif openai_message_type == "response.output_audio.delta":
                b64_audio = openai_response.get("delta", "")
                if not b64_audio:
                    continue

                audio_data = {
                    "event": "media",
                    "streamSid": stream_sid,
                    "media": {"payload": openai_response["delta"]},
                }
                await twilio_ws.send_json(audio_data)

            elif openai_message_type == "response.output_audio_transcript.delta":
                response_id = openai_response.get("response_id")
                if response_id:
                    buffers[response_id] = buffers.get(
                        response_id, ""
                    ) + openai_response.get("delta", "")

            elif openai_message_type == "response.done":
                patching_call = await _handle_response_done(
                    openai_ws, openai_response, buffers, channel, shared_state
                )
                if patching_call:
                    # Wait for any pending audio to be sent
                    await asyncio.sleep(4)
                    await twilio_ws.close()
                    return
            elif openai_message_type == "error":
                print(
                    "[client] OpenAI error (full response):",
                    flush=True,
                )
                print(json.dumps(openai_response, indent=2))

    except Exception as e:
        print(f"Error in send_ai_response: {e}")


@app.websocket("/audio-stream")
async def stream_audio(twilio_ws: WebSocket, language: str = "en-US"):
    await twilio_ws.accept()

    url = "wss://api.openai.com/v1/realtime?model=gpt-realtime"

    headers = {
        "Authorization": f"Bearer {OPENAI_API_KEY}",
        # "OpenAI-Beta": "realtime=v1",
    }

    supabase = await create_async_supabase_client()
    channel = supabase.channel(REALTIME_CHANNEL_NAME)
    await channel.subscribe()

    shared_state = {"stream_sid": None, "call_sid": None, "supabase_client": supabase}
    broadcast_event(channel, LiveEvent.STATE, {"status": CallStatus.IDLE})

    print("Connecting to OpenAI Realtime API...")
    await asyncio.sleep(2)

    broadcast_event(channel, LiveEvent.STATE, {"status": CallStatus.RINGING})

    try:
        async with websockets.connect(
            url, additional_headers=headers, proxy=None, max_size=None
        ) as openai_ws:
            print("✓ Connected to OpenAI Realtime API")
            session_update = build_twilio_session(
                voice=DEFAULT_VOICE,
                instructions=SYSTEM_PROMPT,
                transcription_model="gpt-4o-mini-transcribe",
                silence_duration_ms=DEFAULT_SILENCE_DURATION_MS,
                prefix_padding_ms=DEFAULT_PREFIX_PADDING_MS,
                vad_threshold=0.6,
                idle_timeout_ms=None,
            )
            await openai_ws.send(json.dumps(session_update))
            await asyncio.gather(
                _receive_twilio_stream(twilio_ws, openai_ws, channel, shared_state),
                _send_ai_response(twilio_ws, openai_ws, channel, shared_state),
                return_exceptions=True,
            )
    except Exception as e:
        print("Error in WebSocket connection:", e)
        await twilio_ws.close()


if __name__ == "__main__":
    uvicorn.run("twilio_voice:app", host="127.0.0.1", port=PORT, reload=True)
