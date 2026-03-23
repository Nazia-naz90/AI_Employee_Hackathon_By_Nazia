"""Work-Zone Specialization — determines what each agent (Cloud/Local) owns.

Cloud owns: perception (watchers), triage, drafts, scheduling
Local owns: approvals, WhatsApp session, payments, final execution
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class AgentZone(str, Enum):
    CLOUD = "cloud"
    LOCAL = "local"


@dataclass(frozen=True)
class ZoneCapabilities:
    can_watch_gmail: bool = False
    can_watch_whatsapp: bool = False
    can_watch_facebook: bool = False
    can_watch_linkedin: bool = False
    can_watch_twitter: bool = False
    can_triage_email: bool = False
    can_draft_replies: bool = False
    can_draft_social_posts: bool = False
    can_generate_briefing: bool = False
    can_run_ralph_loops: bool = False
    can_schedule_content: bool = False
    can_create_draft_actions: bool = False
    can_send_email: bool = False
    can_send_whatsapp: bool = False
    can_post_social: bool = False
    can_execute_payment: bool = False
    can_write_dashboard: bool = False
    can_odoo_read: bool = False
    can_odoo_draft: bool = False
    can_odoo_post: bool = False


CLOUD_CAPABILITIES = ZoneCapabilities(
    can_watch_gmail=True,
    can_watch_whatsapp=False,
    can_watch_facebook=True,
    can_watch_linkedin=True,
    can_watch_twitter=True,
    can_triage_email=True,
    can_draft_replies=True,
    can_draft_social_posts=True,
    can_generate_briefing=True,
    can_run_ralph_loops=True,
    can_schedule_content=True,
    can_create_draft_actions=True,
    can_send_email=False,
    can_send_whatsapp=False,
    can_post_social=False,
    can_execute_payment=False,
    can_write_dashboard=False,
    can_odoo_read=True,
    can_odoo_draft=True,
    can_odoo_post=False,
)

LOCAL_CAPABILITIES = ZoneCapabilities(
    can_watch_gmail=False,
    can_watch_whatsapp=True,
    can_watch_facebook=False,
    can_watch_linkedin=False,
    can_watch_twitter=False,
    can_triage_email=True,
    can_draft_replies=True,
    can_draft_social_posts=False,
    can_generate_briefing=False,
    can_run_ralph_loops=True,
    can_schedule_content=False,
    can_create_draft_actions=True,
    can_send_email=True,
    can_send_whatsapp=True,
    can_post_social=True,
    can_execute_payment=True,
    can_write_dashboard=True,
    can_odoo_read=True,
    can_odoo_draft=True,
    can_odoo_post=True,
)


def get_current_zone() -> AgentZone:
    zone_str = os.getenv("AGENT_ZONE", "local").lower()
    try:
        return AgentZone(zone_str)
    except ValueError:
        return AgentZone.LOCAL


def get_capabilities(zone: AgentZone | None = None) -> ZoneCapabilities:
    if zone is None:
        zone = get_current_zone()
    return CLOUD_CAPABILITIES if zone == AgentZone.CLOUD else LOCAL_CAPABILITIES


@dataclass
class ClaimManager:
    """Implements claim-by-move rule for multi-agent coordination.

    First agent to move a file from Needs_Action/ to In_Progress/<agent>/
    owns it. Other agents must ignore files already in In_Progress/.
    """
    vault_path: Path
    agent_name: str

    @property
    def in_progress_dir(self) -> Path:
        return self.vault_path / "In_Progress" / self.agent_name

    def claim(self, source_file: Path) -> Path | None:
        in_progress_root = self.vault_path / "In_Progress"
        if in_progress_root.exists():
            for agent_dir in in_progress_root.iterdir():
                if agent_dir.is_dir():
                    claimed = agent_dir / source_file.name
                    if claimed.exists():
                        return None
        self.in_progress_dir.mkdir(parents=True, exist_ok=True)
        dest = self.in_progress_dir / source_file.name
        try:
            source_file.rename(dest)
            return dest
        except (OSError, FileNotFoundError):
            return None

    def release(self, file_path: Path, destination: Path) -> Path:
        destination.mkdir(parents=True, exist_ok=True)
        dest = destination / file_path.name
        file_path.rename(dest)
        return dest

    def list_claimed(self) -> list[Path]:
        if not self.in_progress_dir.exists():
            return []
        return list(self.in_progress_dir.glob("*.md"))
