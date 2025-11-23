import asyncio
import logging
import os
from enum import StrEnum

from realtime import AsyncRealtimeChannel
from supabase import acreate_client, create_client

REALTIME_CHANNEL_NAME = "live"

# TODO: extract `CallStatus` enum
logger = logging.getLogger(__name__)


class LiveEvent(StrEnum):
    STATE = "state"
    TRANSCRIPT = "transcript"


async def create_async_supabase_client():
    """Throws if SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY env vars are not set."""
    supabase_url, supabase_key = _get_supabase_credentials()
    supabase = await acreate_client(supabase_url, supabase_key)
    return supabase


def create_supabase_client():
    """Throws if SUPABASE_URL or SUPABASE_PUBLISHABLE_KEY env vars are not set."""
    supabase_url, supabase_key = _get_supabase_credentials()
    supabase = create_client(supabase_url, supabase_key)
    return supabase


def _get_supabase_credentials():
    supabase_url = os.environ.get("SUPABASE_URL")
    if supabase_url is None:
        raise ValueError("SUPABASE_URL environment variable is not set")

    supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if supabase_key is None:
        raise ValueError("SUPABASE_PUBLISHABLE_KEY environment variable is not set")

    return supabase_url, supabase_key


def broadcast_event(channel: AsyncRealtimeChannel, event: LiveEvent, payload: dict):
    """Sends `text` to supabase real-time channel."""
    logger.debug(f"Broadcasting event {event} with payload {payload}")
    asyncio.create_task(channel.send_broadcast(event, payload))


async def fetch_challenge(
    supabase: AsyncRealtimeChannel, name: str
) -> dict[str, str] | None:
    """Fetches security question and answer for `name` from Supabase."""
    name = name.lower()
    logger.debug(f"Fetching challenge for {name}")

    # TODO: dynamic fetch

    if name == "mom":
        return {
            "question": "What was our favourite beach you grew up going to?",
            "answer": "Muizenberg",  # real playas know
        }

    elif name == "dad":
        return {
            "question": "What was our first dog's name?",
            "answer": "Maximillian",  # lol never
        }

    elif name == "david":
        return {
            "question": "What colour do we agree is the best jelly bean?",
            "answer": "Purple",
        }

    return {
        "question": "When does Gandalf arrive?",
        "answer": "Exactly on time",
    }
