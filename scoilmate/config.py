"""Runtime settings, read from environment variables.

Defaults are safe for a *server*; `run_local_testing` switches on preview conveniences
(draft practice) explicitly. Tests mutate `settings` attributes directly.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _flag(name: str, default: bool) -> bool:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    if value not in ("0", "1"):
        raise ValueError(f"{name} must be 0 or 1")
    return value == "1"


@dataclass
class Settings:
    db_path: Path = field(
        default_factory=lambda: Path(
            os.environ.get("SCOILMATE_DB", ROOT / "instance" / "scoilmate.db")
        )
    )
    # Secure + __Host- cookie prefix. Turn on whenever the site is served over HTTPS.
    secure_cookies: bool = field(default_factory=lambda: _flag("SCOILMATE_SECURE_COOKIES", False))
    # Let students practise draft (unreviewed) content. Preview only; off by default.
    allow_draft_practice: bool = field(
        default_factory=lambda: _flag("SCOILMATE_ALLOW_DRAFT_PRACTICE", False)
    )
    # Login rate limits (failed attempts per window).
    login_window_s: int = 15 * 60
    login_max_per_account: int = 5
    login_max_per_ip: int = 30

    @property
    def session_cookie(self) -> str:
        return "__Host-scoilmate_session" if self.secure_cookies else "scoilmate_session"

    @property
    def csrf_cookie(self) -> str:
        return "__Host-scoilmate_csrf" if self.secure_cookies else "scoilmate_csrf"


settings = Settings()
