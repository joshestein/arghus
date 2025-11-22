import os

from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()


def main():
    supabase_url = os.environ.get("SUPABASE_URL")
    if supabase_url is None:
        raise ValueError("SUPABASE_URL environment variable is not set")

    supabase_key = os.environ.get("SUPABASE_PUBLISHABLE_KEY")
    if supabase_key is None:
        raise ValueError("SUPABASE_PUBLISHABLE_KEY environment variable is not set")

    supabase: Client = create_client(supabase_url, supabase_key)

    active_calls = supabase.table("active_calls").select("*").execute()
    print(active_calls.data)


if __name__ == "__main__":
    main()
