#!/usr/bin/env python3
# tools/get_token.py
import os

import httpx


def get_access_token(
    email: str, password: str, supabase_url: str, anon_key: str
) -> str:
    url = f"{supabase_url.rstrip('/')}/auth/v1/token?grant_type=password"
    headers = {"apikey": anon_key, "Content-Type": "application/json"}
    payload = {"email": email, "password": password}
    r = httpx.post(url, headers=headers, json=payload)
    r.raise_for_status()
    return r.json()["access_token"]


if __name__ == "__main__":
    SUPABASE_URL = os.getenv("SUPABASE_URL")
    SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
    EMAIL = os.getenv("SUPABASE_EMAIL")
    PASSWORD = os.getenv("SUPABASE_PASSWORD")
    if not all([SUPABASE_URL, SUPABASE_ANON_KEY, EMAIL, PASSWORD]):
        raise SystemExit(
            "Set SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_EMAIL, SUPABASE_PASSWORD"
        )
    print(get_access_token(EMAIL, PASSWORD, SUPABASE_URL, SUPABASE_ANON_KEY))
