import os
from supabase import acreate_client, create_client


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
