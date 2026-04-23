"""Community Archive helpers — fetch following lists and tweets via Supabase."""

import requests

SUPABASE_URL = "https://fabxmporizzqflnftavs.supabase.co"
ANON_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZhYnhtcG9yaXp6cWZsbmZ0YXZzIiwicm9sZSI6ImFub24iLCJpYXQiOjE3MjIyNDQ5MTIsImV4cCI6MjAzNzgyMDkxMn0.UIEJiUNkLsW28tBHmG-RQDW-I5JNlJLt62CSk9D_qG8"
HEADERS = {"apikey": ANON_KEY, "Authorization": f"Bearer {ANON_KEY}"}

PAGE_SIZE = 1000  # Supabase max per request


def _paginated_get(endpoint: str, params: str = "") -> list[dict]:
    """Fetch all rows from a Supabase endpoint, paginating as needed."""
    all_rows = []
    offset = 0
    while True:
        sep = "&" if params else ""
        url = f"{SUPABASE_URL}/rest/v1/{endpoint}?{params}{sep}limit={PAGE_SIZE}&offset={offset}"
        r = requests.get(url, headers=HEADERS, timeout=30)
        r.raise_for_status()
        batch = r.json()
        all_rows.extend(batch)
        if len(batch) < PAGE_SIZE:
            break
        offset += PAGE_SIZE
    return all_rows


def get_all_archive_accounts() -> dict:
    """Returns {account_id: {username, account_display_name, ...}} for all archive users."""
    rows = _paginated_get("account", "select=account_id,username,account_display_name")
    return {a["account_id"]: a for a in rows}


def find_account(username: str) -> dict | None:
    """Find an account by username (case-insensitive)."""
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/account?username=ilike.{username}&select=account_id,username,account_display_name",
        headers=HEADERS, timeout=10,
    )
    r.raise_for_status()
    results = r.json()
    return results[0] if results else None


def get_following_in_archive(username: str) -> list[dict]:
    """Get all accounts that `username` follows AND are in the archive."""
    account = find_account(username)
    if not account:
        return []

    # Get ALL following IDs (paginated)
    rows = _paginated_get("following", f"account_id=eq.{account['account_id']}&select=following_account_id")
    following_ids = {f["following_account_id"] for f in rows}

    if not following_ids:
        return []

    # Intersect with archive accounts
    all_accounts = get_all_archive_accounts()
    return [
        all_accounts[fid]
        for fid in following_ids
        if fid in all_accounts
    ]


def get_tweets(account_id: str, limit: int = 50, since: str = None) -> list[dict]:
    """Get tweets for an account. Optional `since` date (YYYY-MM-DD)."""
    params = f"account_id=eq.{account_id}&select=tweet_id,full_text,created_at,retweet_count,favorite_count&order=created_at.desc&limit={limit}"
    if since:
        params += f"&created_at=gte.{since}T00:00:00"
    r = requests.get(
        f"{SUPABASE_URL}/rest/v1/tweets?{params}",
        headers=HEADERS, timeout=30,
    )
    r.raise_for_status()
    return r.json()
