import os
import time

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SEED_ID = 1


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


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    if supabase_url is None:
        raise ValueError("SUPABASE_URL environment variable is not set")

    supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if supabase_key is None:
        raise ValueError("SUPABASE_PUBLISHABLE_KEY environment variable is not set")

    supabase: Client = create_client(supabase_url, supabase_key)

    reset_simulation(supabase)

    print("📞 Incoming call...")
    supabase.table("active_calls").update({"status": "RINGING"}).eq(
        "id", SEED_ID
    ).execute()
    time.sleep(2)

    print("🛡️ Call intercepted...")

    supabase.table("active_calls").update(
        {"status": "ANALYZING", "transcript": "Listening..."}
    ).eq("id", SEED_ID).execute()


if __name__ == "__main__":
    main()
