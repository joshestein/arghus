import asyncio

from dotenv import load_dotenv
from realtime import AsyncRealtimeChannel
from supabase import Client, AsyncClient

from supabase_utils import (
    create_async_supabase_client,
    create_supabase_client,
    broadcast_event,
)

load_dotenv()

SEED_ID = 1

LIVE_TRANSCRIPT = """
(Sobbing) Hi... it's Mom. I don't have much time. 
I'm at the police station. My phone was stolen, so I'm using the officer's phone.
I need you to wire bail money immediately. Please, I'm scared. 
Don't call dad, just send the money to this account number...
"""

REALTIME_CHANNEL_NAME = "live_call"
REALTIME_EVENT_TRANSCRIPT = "transcript"
REALTIME_EVENT_THREAT = "threat"




def reset_simulation(supabase: Client):
    print("Resetting state...")
    data = {
        "status": "IDLE",
        "transcript": "",
        "threat_score": 0,
        "threat_reason": "",
        "suggested_question": "",
    }
    supabase.table("active_calls").update(data).eq("id", SEED_ID).execute()


async def simulate_transcription(channel: AsyncRealtimeChannel):
    current_transcript = ""
    for i, word in enumerate(LIVE_TRANSCRIPT.split()):
        if i % 5 == 0:  # Update DB every 5 words to avoid rate limit
            current_transcript += " " + word
            broadcast_event(
                channel, REALTIME_EVENT_TRANSCRIPT, {"text": current_transcript}
            )
        else:
            current_transcript += " " + word

        await asyncio.sleep(0.15)  # Match reading speed to audio speed

        # Stop "streaming" to indicate alert has been triggered
        if i == 20:
            break


async def main():
    supabase = create_supabase_client()
    reset_simulation(supabase)

    print("📞 Incoming call...")
    supabase.table("active_calls").update({"status": "RINGING"}).eq(
        "id", SEED_ID
    ).execute()
    await asyncio.sleep(1)

    print("🛡️ Call intercepted...")

    supabase.table("active_calls").update(
        {"status": "ANALYZING", "transcript": "Listening..."}
    ).eq("id", SEED_ID).execute()

    supabase_async: AsyncClient = await create_async_supabase_client()
    channel = supabase_async.channel(REALTIME_CHANNEL_NAME)
    await channel.subscribe()
    await simulate_transcription(channel)

    supabase.table("active_calls").update({"status": "THREAT_DETECTED"}).eq(
        "id", SEED_ID
    ).execute()

    broadcast_event(
        channel,
        REALTIME_EVENT_THREAT,
        {
            "status": "THREAT_DETECTED",
            "score": 75,
            "reason": "Financial Urgency",
            "question": "Where did we go for childhood holidays?",
        },
    )


if __name__ == "__main__":
    asyncio.run(main())
