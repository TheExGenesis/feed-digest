#!/usr/bin/env python3
"""hermes-feed deliver — send latest digest via email (CLI fallback for non-agent setups)."""

import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(SKILL_DIR / "scripts"))

from sources._base import get_config, get_state_db, log_pipeline


def deliver_email(skill_dir: Path, digest_id: str = None, dry_run: bool = False):
    config = get_config(skill_dir)
    conn = get_state_db(skill_dir)

    if not digest_id:
        row = conn.execute(
            "SELECT digest_id FROM digests WHERE status='composed' ORDER BY created_at DESC LIMIT 1"
        ).fetchone()
        if not row:
            print("No undelivered digests found.")
            return
        digest_id = row["digest_id"]

    digest_path = skill_dir / "digests" / f"{digest_id}.md"
    if not digest_path.exists():
        print(f"Digest file not found: {digest_path}")
        return

    content = digest_path.read_text(encoding="utf-8")
    email_cfg = config.get("email", {})
    to_addr = email_cfg.get("to", "")
    from_addr = email_cfg.get("from", email_cfg.get("smtp_user", ""))

    msg = MIMEText(content, "plain", "utf-8")
    msg["Subject"] = f"Feed Digest — {digest_id}"
    msg["From"] = from_addr
    msg["To"] = to_addr

    if dry_run:
        dry_dir = skill_dir / "delivered" / "dryrun"
        dry_dir.mkdir(parents=True, exist_ok=True)
        (dry_dir / f"{digest_id}.eml").write_text(msg.as_string(), encoding="utf-8")
        print(f"Dry run: wrote {dry_dir / f'{digest_id}.eml'}")
    else:
        password_env = email_cfg.get("smtp_password_env", "FEED_SMTP_PASSWORD")
        password = os.environ.get(password_env, "")
        if not password:
            print(f"SMTP password not set. Export {password_env} and retry.")
            log_pipeline(skill_dir, "deliver", "error", error=f"missing {password_env}")
            return

        try:
            with smtplib.SMTP(email_cfg.get("smtp_host", ""), email_cfg.get("smtp_port", 587)) as server:
                server.starttls()
                server.login(email_cfg.get("smtp_user", ""), password)
                server.sendmail(from_addr, [to_addr], msg.as_string())
            print(f"Delivered {digest_id} to {to_addr}")
        except Exception as e:
            log_pipeline(skill_dir, "deliver", "error", error=str(e))
            print(f"Delivery failed: {e}")
            return

    conn.execute(
        "INSERT OR REPLACE INTO deliveries (digest_id, delivered_at, channel) VALUES (?, datetime('now'), ?)",
        (digest_id, "dryrun" if dry_run else "email"),
    )
    conn.commit()
    conn.close()
    log_pipeline(skill_dir, "deliver", "ok", digest_id=digest_id, dry_run=dry_run)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("digest_id", nargs="?")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    deliver_email(SKILL_DIR, args.digest_id, args.dry_run)
