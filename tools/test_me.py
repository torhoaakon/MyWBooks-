#!/usr/bin/env python3
# tools/test_me.py
import dotenv

dotenv.load_dotenv()

import os

import httpx

from .get_token import get_access_token

API_URL = os.getenv("API_URL", "http://127.0.0.1:8001")


def main():
    supabase_url = os.getenv("SUPABASE_URL")
    anon_key = os.getenv("SUPABASE_ANON_KEY")
    email = os.getenv("SUPABASE_EMAIL")
    password = os.getenv("SUPABASE_PASSWORD")
    if not all([supabase_url, anon_key, email, password]):
        raise SystemExit(
            "Set SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_EMAIL, SUPABASE_PASSWORD"
        )

    token = get_access_token(email, password, supabase_url, anon_key)
    r = httpx.get(f"{API_URL}/me", headers={"Authorization": f"Bearer {token}"})
    print("Status:", r.status_code)
    print("Response:", r.json())


if __name__ == "__main__":
    main()
