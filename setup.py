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
    if existing:
        print(f"{question}: already set in ${env_var}")
        return ""
    value = input(f"{question} (will be saved to .env, NOT config.yaml): ").strip()
    return value


def main():
    config_path = SKILL_DIR / "config.yaml"
    env_path = SKILL_DIR / ".env"

    print("=" * 60)
    print("  feed-digest setup")
    print("=" * 60)
    print()

    # Memory path
    memory_path = prompt("Path to your memory folder (read-only context for the agent)",
                         "~/hermes/memory")

    # Timezone
    timezone = prompt("Your timezone (IANA format)", "America/New_York")

    # Email
    print("\n--- Email delivery ---")
    smtp_host = prompt("SMTP host", "smtp.gmail.com")
    smtp_port = int(prompt("SMTP port", "587"))
    smtp_user = prompt("SMTP username (your email)")
    from_addr = prompt("From address", smtp_user)
    to_addr = prompt("Deliver digests to (email address)", smtp_user)

    # API key (OpenRouter)
    print("\n--- LLM API (OpenRouter) ---")
    api_key = prompt_secret("OpenRouter API key", "OPENROUTER_API_KEY")

    # Sources
    print("\n--- Sources ---")
    substacks = prompt_list("Substack URLs to follow:",
                            "https://xiqo.substack.com")
    twitter_handles = prompt_list("Twitter handles (community archive only, no @):",
                                  "frsc")
    blog_feeds = prompt_list("Blog RSS feed URLs:",
                             "https://simonwillison.net/atom.xml")

    # Serving
    print("\n--- Serving (for stable digest URLs) ---")
    serve_port = int(prompt("Local serve port", "7700"))
    public_url = prompt("Public base URL (if behind a proxy, else leave default)",
                        f"http://localhost:{serve_port}")

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
            "model": "anthropic/claude-sonnet-4",
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
        "digest": {
            "max_items": 7,
            "tail_items": 10,
            "integration_window_days": 7,
            "token_budget": 150000,
        },
    }

    # Write config.yaml
    with open(config_path, "w") as f:
        yaml.dump(config, f, default_flow_style=False, sort_keys=False)
    print(f"\nWrote {config_path}")

    # Write .env (secrets)
    env_lines = []
    if api_key:
        env_lines.append(f"OPENROUTER_API_KEY={api_key}")
    smtp_password = prompt_secret("SMTP password (for email delivery)", "FEED_SMTP_PASSWORD")
    if smtp_password:
        env_lines.append(f"FEED_SMTP_PASSWORD={smtp_password}")

    if env_lines:
        with open(env_path, "w") as f:
            f.write("\n".join(env_lines) + "\n")
        os.chmod(env_path, 0o600)
        print(f"Wrote {env_path} (chmod 600)")
    else:
        print("No secrets to write (already in environment).")

    # Update .gitignore if .env not already there
    gitignore_path = SKILL_DIR / ".gitignore"
    if gitignore_path.exists():
        content = gitignore_path.read_text()
        if ".env" not in content:
            with open(gitignore_path, "a") as f:
                f.write("\n.env\n")
            print("Added .env to .gitignore")

    print()
    print("=" * 60)
    print("  Setup complete!")
    print("=" * 60)
    print()
    print("Next steps:")
    print(f"  1. Source secrets:  source {env_path}")
    print(f"     Or export them: export $(cat {env_path} | xargs)")
    print(f"  2. Test ingest:    ./hermes-feed ingest")
    print(f"  3. Test digest:    ./hermes-feed digest")
    print(f"  4. Install cron:   crontab -e")
    print(f"       0 7 * * * cd {SKILL_DIR} && source .env && source .venv/bin/activate && ./hermes-feed ingest && ./hermes-feed digest")


if __name__ == "__main__":
    main()
