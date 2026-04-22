#!/usr/bin/env python3
"""Interactive setup flow for feed-digest. Prompts for config values, writes config.yaml."""

import os
import sys
from pathlib import Path

import yaml

SKILL_DIR = Path(__file__).resolve().parent


def prompt(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    answer = input(f"{question}{hint}: ").strip()
    return answer or default


def prompt_yn(question: str, default: bool = True) -> bool:
    hint = "[Y/n]" if default else "[y/N]"
    answer = input(f"{question} {hint}: ").strip().lower()
    if not answer:
        return default
    return answer in ("y", "yes")


def prompt_list(question: str, example: str = "") -> list[str]:
    print(f"{question}")
    if example:
        print(f"  (example: {example})")
    print("  Enter one per line. Empty line to finish.")
    items = []
    while True:
        item = input("  > ").strip()
        if not item:
            break
        items.append(item)
    return items


def prompt_secret(question: str, env_var: str) -> str:
    existing = os.environ.get(env_var, "")
    env_path = SKILL_DIR / ".env"
    if not existing and env_path.exists():
        for line in env_path.read_text().splitlines():
            if line.startswith(f"{env_var}="):
                existing = line.split("=", 1)[1].strip()
    if existing:
        masked = existing[:8] + "..." + existing[-4:] if len(existing) > 16 else "***"
        print(f"{question}: found ({masked})")
        if prompt_yn("  Keep existing?"):
            return ""
    value = input(f"{question} (saved to .env, NOT config.yaml): ").strip()
    return value


def fetch_substack_subscriptions(username: str) -> list[str]:
    try:
        from substack_api import User
        print(f"  Fetching subscriptions for {username}...")
        user = User(username)
        subs = user.get_subscriptions()
        urls = []
        for sub in subs:
            if isinstance(sub, dict):
                url = sub.get("domain") or sub.get("url") or sub.get("base_url")
                name = sub.get("publication_name") or sub.get("name") or ""
                if url:
                    if not url.startswith("http"):
                        url = f"https://{url}"
                    urls.append(url)
                    print(f"    + {name or url}")
        if not urls:
            # Try alternate structure
            for sub in subs:
                if isinstance(sub, str):
                    urls.append(sub)
                    print(f"    + {sub}")
        return urls
    except Exception as e:
        print(f"  Could not fetch subscriptions: {e}")
        print("  You can add Substack URLs manually instead.")
        return []


def setup_substacks() -> list[str]:
    print("\n  Substack sources:")
    choice = prompt("  (a) Import all my Substack subscriptions\n"
                     "  (b) Enter URLs manually\n"
                     "  (c) Both — import subs + add extras\n"
                     "  Choose", "a")

    urls = []
    if choice in ("a", "c"):
        username = prompt("  Your Substack username (the part before .substack.com)")
        if username:
            fetched = fetch_substack_subscriptions(username)
            if fetched:
                print(f"  Found {len(fetched)} subscriptions.")
                if prompt_yn(f"  Add all {len(fetched)} to your feed?"):
                    urls.extend(fetched)
                else:
                    print("  Enter the numbers to keep (comma-separated), or 'all':")
                    for i, u in enumerate(fetched):
                        print(f"    {i+1}. {u}")
                    selection = input("  > ").strip()
                    if selection.lower() == "all":
                        urls.extend(fetched)
                    else:
                        for idx in selection.replace(",", " ").split():
                            try:
                                urls.append(fetched[int(idx) - 1])
                            except (ValueError, IndexError):
                                pass

    if choice in ("b", "c") or not urls:
        manual = prompt_list("  Additional Substack URLs:",
                             "https://xiqo.substack.com")
        urls.extend(manual)

    # Dedup
    seen = set()
    unique = []
    for u in urls:
        normalized = u.rstrip("/").lower()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(u)

    return unique


def setup_twitter() -> list[str]:
    print("\n  Twitter sources (Community Archive):")
    choice = prompt("  (a) Import everyone I follow who's in the archive\n"
                     "  (b) Enter handles manually\n"
                     "  (c) Both — import following + add extras\n"
                     "  Choose", "a")

    handles = []
    if choice in ("a", "c"):
        username = prompt("  Your Twitter/X username (no @)", "exgenesis")
        if username:
            try:
                import sys
                sys.path.insert(0, str(SKILL_DIR / "scripts"))
                from sources.community_archive import get_following_in_archive
                print(f"  Looking up @{username} in the Community Archive...")
                following = get_following_in_archive(username)
                if following:
                    print(f"  Found {len(following)} accounts you follow in the archive:")
                    for a in sorted(following, key=lambda x: x["username"].lower()):
                        print(f"    @{a['username']} ({a.get('account_display_name', '')})")
                    if prompt_yn(f"\n  Add all {len(following)}?"):
                        handles.extend(a["username"] for a in following)
                    else:
                        print("  Enter the numbers to keep (comma-separated), or 'all':")
                        sorted_following = sorted(following, key=lambda x: x["username"].lower())
                        for i, a in enumerate(sorted_following):
                            print(f"    {i+1}. @{a['username']}")
                        selection = input("  > ").strip()
                        if selection.lower() == "all":
                            handles.extend(a["username"] for a in sorted_following)
                        else:
                            for idx in selection.replace(",", " ").split():
                                try:
                                    handles.append(sorted_following[int(idx) - 1]["username"])
                                except (ValueError, IndexError):
                                    pass
                else:
                    print(f"  @{username} not found in archive or has no following data.")
            except Exception as e:
                print(f"  Could not fetch from Community Archive: {e}")
                print("  You can add handles manually instead.")

    if choice in ("b", "c") or not handles:
        manual = prompt_list("  Additional Twitter handles (no @):", "eigenrobot")
        handles.extend(manual)

    # Dedup
    seen = set()
    unique = []
    for h in handles:
        h_lower = h.lower().strip("@")
        if h_lower not in seen:
            seen.add(h_lower)
            unique.append(h_lower)

    return unique


def main():
    config_path = SKILL_DIR / "config.yaml"
    env_path = SKILL_DIR / ".env"

    # Load existing config if present
    existing_config = {}
    if config_path.exists():
        with open(config_path) as f:
            existing_config = yaml.safe_load(f) or {}

    existing_sources = existing_config.get("sources", {})

    print("=" * 60)
    print("  feed-digest setup")
    print("=" * 60)
    print()

    # Memory path
    memory_path = prompt("Path to your memory folder",
                         existing_config.get("memory_path", "~/hermes/memory"))

    # Timezone
    timezone = prompt("Your timezone (IANA format)",
                      existing_config.get("timezone", "America/New_York"))

    # Email
    existing_email = existing_config.get("email", {})
    print("\n--- Email delivery ---")
    smtp_host = prompt("SMTP host", existing_email.get("smtp_host", "smtp.gmail.com"))
    smtp_port = int(prompt("SMTP port", str(existing_email.get("smtp_port", 587))))
    smtp_user = prompt("SMTP username (your email)",
                       existing_email.get("smtp_user", ""))
    from_addr = prompt("From address", existing_email.get("from", smtp_user))
    to_addr = prompt("Deliver digests to", existing_email.get("to", smtp_user))

    # API key (OpenRouter)
    print("\n--- LLM API (OpenRouter) ---")
    api_key = prompt_secret("OpenRouter API key", "OPENROUTER_API_KEY")

    # Sources
    print("\n--- Sources ---")

    # Substack — smart import
    substacks = setup_substacks()
    if not substacks and existing_sources.get("substack"):
        print(f"  Keeping existing {len(existing_sources['substack'])} Substack sources.")
        substacks = existing_sources["substack"]

    # Twitter (Community Archive)
    twitter_handles = setup_twitter()
    if not twitter_handles and existing_sources.get("twitter_community_archive"):
        print(f"  Keeping existing {len(existing_sources['twitter_community_archive'])} Twitter handles.")
        twitter_handles = existing_sources["twitter_community_archive"]

    # Blogs
    blog_feeds = prompt_list("Blog RSS feed URLs:",
                             "https://simonwillison.net/atom.xml")
    if not blog_feeds and existing_sources.get("blog_rss"):
        print(f"  Keeping existing {len(existing_sources['blog_rss'])} blog feeds.")
        blog_feeds = existing_sources["blog_rss"]

    # Serving
    existing_serve = existing_config.get("serve", {})
    print("\n--- Serving (for stable digest URLs) ---")
    serve_port = int(prompt("Local serve port",
                            str(existing_serve.get("port", 7700))))
    public_url = prompt("Public base URL",
                        existing_serve.get("public_base_url", f"http://localhost:{serve_port}"))

    # LLM model
    existing_llm = existing_config.get("llm", {})
    model = prompt("LLM model (OpenRouter model ID)",
                   existing_llm.get("model", "anthropic/claude-sonnet-4"))

    # Build config
    config = {
        "memory_path": memory_path,
        "timezone": timezone,
        "email": {
            "smtp_host": smtp_host,
            "smtp_port": smtp_port,
            "smtp_user": smtp_user,
            "smtp_password_env": "FEED_SMTP_PASSWORD",
            "from": from_addr,
            "to": to_addr,
        },
        "llm": {
            "provider": "openrouter",
            "base_url": "https://openrouter.ai/api/v1",
            "api_key_env": "OPENROUTER_API_KEY",
            "model": model,
        },
        "sources": {
            "substack": substacks,
            "twitter_community_archive": twitter_handles,
            "blog_rss": blog_feeds,
        },
        "serve": {
            "bind_host": "127.0.0.1",
            "port": serve_port,
            "public_base_url": public_url,
        },
        "digest": existing_config.get("digest", {
            "max_items": 7,
            "tail_items": 10,
            "integration_window_days": 7,
            "token_budget": 150000,
        }),
    }

    # Write config.yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"\nWrote {config_path}")

    # Summary
    print(f"\n  Sources configured:")
    print(f"    Substacks:       {len(substacks)}")
    print(f"    Twitter handles: {len(twitter_handles)}")
    print(f"    Blog RSS feeds:  {len(blog_feeds)}")

    # Write .env (secrets) — preserve existing values
    existing_env = {}
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                existing_env[k.strip()] = v.strip()

    if api_key:
        existing_env["OPENROUTER_API_KEY"] = api_key
    smtp_password = prompt_secret("SMTP password (for email delivery)", "FEED_SMTP_PASSWORD")
    if smtp_password:
        existing_env["FEED_SMTP_PASSWORD"] = smtp_password

    if existing_env:
        with open(env_path, "w") as f:
            f.write("\n".join(f"{k}={v}" for k, v in existing_env.items()) + "\n")
        os.chmod(env_path, 0o600)
        print(f"Wrote {env_path} (chmod 600)")

    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  1. Test ingest:    ./hermes-feed ingest")
    print(f"  2. Test digest:    ./hermes-feed digest")
    print(f"  3. Install cron:   crontab -e")
    print(f"       0 7 * * * cd {SKILL_DIR} && export $(cat .env | xargs) && source .venv/bin/activate && ./hermes-feed ingest && ./hermes-feed digest")


if __name__ == "__main__":
    main()
