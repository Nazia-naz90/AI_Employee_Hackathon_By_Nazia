from __future__ import annotations
import contextlib
"""Cloud Orchestrator — extends base Orchestrator for cloud deployment.

CloudOrchestrator:
  - Filters watchers based on zone capabilities (no WhatsApp, no Instagram)
  - Runs _cloud_draft_loop() to process Needs_Action items and create drafts
  - Writes drafts to Pending_Approval/ for local agent to execute

LocalOrchestrator:
  - Extends CloudOrchestrator
  - Adds _merge_updates_loop() to merge Cloud signals into Dashboard.md
  - Owns WhatsApp session, payments, final execution
"""


import asyncio
import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from backend.orchestrator.orchestrator import Orchestrator, OrchestratorConfig
from backend.cloud.agent_role import AgentZone, get_capabilities, ZoneCapabilities

if TYPE_CHECKING:
    from backend.orchestrator.watchdog import WatcherTask

logger = logging.getLogger(__name__)


class CloudOrchestrator(Orchestrator):
    """Orchestrator for cloud deployment.

    Filters watchers based on zone capabilities:
      - Cloud CAN run: Gmail, Facebook, LinkedIn, Twitter
      - Cloud CANNOT run: WhatsApp, Instagram (require local browser session)

    Additional responsibilities:
      - _cloud_draft_loop(): Scans Needs_Action/ for new items
        - Triage emails → draft replies in Pending_Approval/
        - Social mentions → draft posts in Pending_Approval/
        - Ralph loop tasks → spawn loops, move results to Done/
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        super().__init__(config)
        self.capabilities = get_capabilities(AgentZone.CLOUD)
        self._cloud_draft_task: asyncio.Task[None] | None = None

    def _acquire_lock(self) -> bool:
        """Acquire orchestrator lock file."""
        from backend.orchestrator.orchestrator import acquire_lock
        return acquire_lock(self.config.lock_file_path)

    def _build_watcher_configs(self) -> list[tuple[str, Callable[[], object]]]:
        """Build watcher configs filtered by cloud zone capabilities.

        Returns:
            List of (name, factory) tuples for watchers the cloud zone can run.
        """
        configs: list[tuple[str, Callable[[], object]]] = []

        # Gmail Watcher (cloud CAN run)
        if self.capabilities.can_watch_gmail:
            def _gmail_factory():  # noqa: ANN202
                from backend.watchers.gmail_watcher import GmailWatcher

                return GmailWatcher(
                    vault_path=str(self.vault_path),
                    credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "config/credentials.json"),
                    token_path=os.getenv("GMAIL_TOKEN_PATH", "config/token.json"),
                    check_interval=int(os.getenv("GMAIL_CHECK_INTERVAL", "120")),
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Gmail", _gmail_factory))

        # Vault Action Watcher (always available)
        def _vault_action_factory():  # noqa: ANN202
            from backend.watchers.vault_action_watcher import VaultActionWatcher

            return VaultActionWatcher(
                vault_path=str(self.vault_path),
                check_interval=5,
            )

        configs.append(("VaultAction", _vault_action_factory))

        # WhatsApp Watcher (cloud CANNOT run - requires local browser)
        # Skipped in cloud zone

        # LinkedIn Watcher (cloud CAN run)
        if self.capabilities.can_watch_linkedin:
            def _linkedin_factory():  # noqa: ANN202
                from backend.watchers.linkedin_watcher import LinkedInWatcher

                return LinkedInWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("LINKEDIN_SESSION_PATH", "config/linkedin_session"),
                    check_interval=300,
                    headless=os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("LinkedIn", _linkedin_factory))

        # Facebook Watcher (cloud CAN run)
        if self.capabilities.can_watch_facebook:
            def _facebook_factory():  # noqa: ANN202
                from backend.watchers.facebook_watcher import FacebookWatcher

                keywords_env = os.getenv("FACEBOOK_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return FacebookWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("FACEBOOK_SESSION_PATH", "config/meta_session"),
                    check_interval=int(os.getenv("FACEBOOK_CHECK_INTERVAL", "120")),
                    keywords=keywords,
                    headless=os.getenv("FACEBOOK_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Facebook", _facebook_factory))

        # Instagram Watcher (cloud CANNOT run - requires local browser)
        # Skipped in cloud zone

        # Twitter Watcher (cloud CAN run)
        if self.capabilities.can_watch_twitter:
            def _twitter_factory():  # noqa: ANN202
                from backend.watchers.twitter_watcher import TwitterWatcher

                keywords_env = os.getenv("TWITTER_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return TwitterWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("TWITTER_SESSION_PATH", "config/twitter_session"),
                    check_interval=int(os.getenv("TWITTER_CHECK_INTERVAL", "300")),
                    keywords=keywords,
                    headless=os.getenv("TWITTER_HEADLESS", "false").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Twitter", _twitter_factory))

        return configs

    async def run(self) -> None:
        """Main entry point for cloud orchestrator.

        Extends base run() to also start the cloud draft loop.
        """
        if not self._acquire_lock():
            logger.error("Cannot start: another orchestrator instance is running")
            return

        try:
            self._started_at = self._now_iso()
            self._log_event("orchestrator_start", "success", f"DEV_MODE={self.config.dev_mode} ZONE=cloud")

            mode = "DEV_MODE" if self.config.dev_mode else "PRODUCTION"
            logger.info("Starting cloud orchestrator (%s)", mode)

            # Check content schedule on startup
            await self._check_content_schedule()

            # Check CEO briefing schedule on startup (Feature 007)
            await self._check_briefing_schedule()

            # Check for pending Ralph loop tasks (Feature 001)
            await self._check_ralph_loops()

            # Start watchers (filtered by zone capabilities)
            self._start_watchers()

            # Start action executor
            self._start_action_executor()

            # Start dashboard loop
            self._start_dashboard_loop()

            # Start cloud draft loop (cloud-specific)
            self._start_cloud_draft_loop()

            logger.info("Cloud orchestrator running. Press Ctrl+C to stop.")

            # Block until cancelled
            await self._wait_forever()

        finally:
            await self.shutdown()

    def _start_cloud_draft_loop(self) -> None:
        """Start the cloud draft processing loop."""
        self._cloud_draft_task = asyncio.create_task(
            self._cloud_draft_loop(),
            name="cloud-draft-loop",
        )
        logger.info("Started cloud draft loop")

    async def _cloud_draft_loop(self) -> None:
        """Process Needs_Action items and create drafts in Pending_Approval/.

        This loop:
          1. Scans Needs_Action/ for new action files
          2. For emails: triage and draft replies
          3. For social mentions: draft posts/responses
          4. For Ralph loop tasks: spawn loops
          5. Moves processed files to In_Progress/cloud/ or Done/
        """
        from backend.utils.frontmatter import parse_frontmatter, update_frontmatter

        pending_approval = self.vault_path / "Pending_Approval"
        in_progress_cloud = self.vault_path / "In_Progress" / "cloud"
        pending_approval.mkdir(parents=True, exist_ok=True)
        in_progress_cloud.mkdir(parents=True, exist_ok=True)

        while True:
            try:
                await self._process_needs_action_items(
                    pending_approval, in_progress_cloud, parse_frontmatter, update_frontmatter
                )
            except Exception:
                logger.exception("Error in cloud draft loop")
            await asyncio.sleep(self.config.check_interval)

    async def _process_needs_action_items(
        self,
        pending_approval: Path,
        in_progress_cloud: Path,
        parse_frontmatter: Callable,
        update_frontmatter: Callable,
    ) -> None:
        """Process all items in Needs_Action/ directory."""
        needs_action = self.vault_path / "Needs_Action"
        if not needs_action.exists():
            return

        for action_file in sorted(needs_action.glob("*.md")):
            try:
                fm = parse_frontmatter(action_file)
            except Exception:
                logger.warning("Failed to parse frontmatter: %s", action_file)
                continue

            action_type = fm.get("type", "")
            source = fm.get("source", "")

            # Claim the file by moving to In_Progress/cloud/
            claimed_path = self._claim_file(action_file, in_progress_cloud)
            if claimed_path is None:
                continue  # Already claimed by another agent

            try:
                if action_type == "email_reply":
                    await self._draft_email_reply(claimed_path, pending_approval, fm)
                elif action_type in ("social_mention", "social_comment", "social_message"):
                    await self._draft_social_response(claimed_path, pending_approval, fm, source)
                elif action_type == "ralph_loop_task":
                    await self._process_ralph_loop(claimed_path, fm, parse_frontmatter, update_frontmatter)
                else:
                    # Unknown type - leave for local agent
                    self._release_file(claimed_path, needs_action)
            except Exception:
                logger.exception("Failed to process action file: %s", claimed_path)
                # On error, return to Needs_Action
                self._release_file(claimed_path, needs_action)

    def _claim_file(self, source: Path, dest_dir: Path) -> Path | None:
        """Move file from source to dest_dir, claiming it for cloud processing."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        try:
            source.rename(dest)
            logger.debug("Claimed file: %s -> %s", source, dest)
            return dest
        except (OSError, FileNotFoundError) as exc:
            logger.warning("Failed to claim file %s: %s", source, exc)
            return None

    def _release_file(self, source: Path, dest_dir: Path) -> None:
        """Return file to Needs_Action/ for local agent to process."""
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest = dest_dir / source.name
        try:
            source.rename(dest)
            logger.debug("Released file: %s -> %s", source, dest)
        except (OSError, FileNotFoundError) as exc:
            logger.warning("Failed to release file %s: %s", source, exc)

    async def _draft_email_reply(
        self,
        action_file: Path,
        pending_approval: Path,
        frontmatter: dict,
    ) -> None:
        """Create draft email reply in Pending_Approval/.

        Uses the email action template system.
        """
        from backend.utils.timestamps import now_iso

        subject = frontmatter.get("subject", "Re: Email")
        original_from = frontmatter.get("from", "")
        original_date = frontmatter.get("date", "")
        body = frontmatter.get("body", "")

        # Create draft reply
        draft_content = f"""---
type: email_draft
status: pending_approval
created: {self._now_iso()}
source_file: {action_file.name}
original_from: {original_from}
original_date: {original_date}
subject: {subject}
---

# Draft Email Reply

**To**: {original_from}
**Subject**: {subject}

## Original Message

{body}

## Draft Reply

[AI to draft reply here]

---
*Draft created by Cloud Orchestrator. Local agent will execute after approval.*
"""

        draft_path = pending_approval / f"email_draft_{action_file.stem}.md"
        draft_path.write_text(draft_content, encoding="utf-8")
        logger.info("Created email draft: %s", draft_path)

        # Move action file to Done
        done_dir = self.vault_path / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)
        action_file.rename(done_dir / action_file.name)

    async def _draft_social_response(
        self,
        action_file: Path,
        pending_approval: Path,
        frontmatter: dict,
        source: str,
    ) -> None:
        """Create draft social media response in Pending_Approval/."""
        from backend.utils.timestamps import now_iso

        content = frontmatter.get("content", "")
        platform = frontmatter.get("platform", source)
        author = frontmatter.get("author", "Unknown")

        draft_content = f"""---
type: social_draft
status: pending_approval
created: {self._now_iso()}
source_file: {action_file.name}
platform: {platform}
author: {author}
---

# Draft Social Media Response

**Platform**: {platform}
**Author**: {author}

## Original Content

{content}

## Draft Response

[AI to draft response here]

---
*Draft created by Cloud Orchestrator. Local agent will execute after approval.*
"""

        draft_path = pending_approval / f"social_draft_{action_file.stem}.md"
        draft_path.write_text(draft_content, encoding="utf-8")
        logger.info("Created social draft: %s", draft_path)

        # Move action file to Done
        done_dir = self.vault_path / "Done"
        done_dir.mkdir(parents=True, exist_ok=True)
        action_file.rename(done_dir / action_file.name)

    async def _process_ralph_loop(
        self,
        action_file: Path,
        frontmatter: dict,
        parse_frontmatter: Callable,
        update_frontmatter: Callable,
    ) -> None:
        """Process Ralph loop task."""
        from backend.ralph_wiggum.ralph_loop import RalphLoop
        from backend.ralph_wiggum import CompletionStrategy, LoopStatus

        prompt = frontmatter.get("prompt", "")
        if not prompt:
            logger.warning("Ralph loop task has no prompt: %s", action_file)
            return

        strategy_str = frontmatter.get("completion_strategy", "promise")
        try:
            strategy = CompletionStrategy(strategy_str)
        except ValueError:
            strategy = CompletionStrategy.promise

        promise = frontmatter.get("completion_promise", "TASK_COMPLETE")
        file_pattern = frontmatter.get("completion_file_pattern")
        max_iterations = frontmatter.get("max_iterations")
        if max_iterations is not None:
            try:
                max_iterations = int(max_iterations)
            except (ValueError, TypeError):
                max_iterations = None

        loop = RalphLoop(
            vault_path=str(self.vault_path),
            dev_mode=self.config.dev_mode,
            dry_run=self.config.dry_run,
        )

        logger.info("Processing Ralph loop: %s", action_file.name)
        result = await asyncio.to_thread(
            loop.start,
            prompt,
            strategy,
            promise if strategy == CompletionStrategy.promise else None,
            file_pattern if strategy == CompletionStrategy.file_movement else None,
            max_iterations,
        )

        if result.status == LoopStatus.completed:
            # Move to Done
            done_dir = self.vault_path / "Done"
            done_dir.mkdir(parents=True, exist_ok=True)
            action_file.rename(done_dir / action_file.name)
            logger.info("Ralph loop completed: %s", action_file.name)
        elif result.status == LoopStatus.halted:
            # Update frontmatter with halt reason and return to Needs_Action
            halt_val = result.halt_reason.value if result.halt_reason else "unknown"
            try:
                update_frontmatter(action_file, {"ralph_halt_reason": halt_val})
            except Exception:
                pass
            self._release_file(action_file, self.vault_path / "Needs_Action")
            logger.warning("Ralph loop halted: %s, reason=%s", action_file.name, halt_val)

    def _now_iso(self) -> str:
        """Get current timestamp in ISO format."""
        from backend.utils.timestamps import now_iso
        return now_iso()

    async def shutdown(self) -> None:
        """Cancel all tasks including cloud draft loop."""
        logger.info("Shutting down cloud orchestrator...")

        # Cancel cloud draft task
        if self._cloud_draft_task and not self._cloud_draft_task.done():
            self._cloud_draft_task.cancel()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._cloud_draft_task, timeout=5.0)

        await super().shutdown()


class LocalOrchestrator(CloudOrchestrator):
    """Orchestrator for local deployment.

    Extends CloudOrchestrator with:
      - All watchers enabled (including WhatsApp, Instagram)
      - _merge_updates_loop() to merge Cloud signals into Dashboard.md
      - Owns WhatsApp session, payments, final execution
      - Can write to Dashboard.md
    """

    def __init__(self, config: OrchestratorConfig) -> None:
        super().__init__(config)
        self.capabilities = get_capabilities(AgentZone.LOCAL)
        self._merge_updates_task: asyncio.Task[None] | None = None

    def _build_watcher_configs(self) -> list[tuple[str, Callable[[], object]]]:
        """Build watcher configs for local zone (all watchers enabled)."""
        configs: list[tuple[str, Callable[[], object]]] = []

        # Gmail Watcher (local can run but typically cloud handles)
        if self.capabilities.can_watch_gmail:
            def _gmail_factory():  # noqa: ANN202
                from backend.watchers.gmail_watcher import GmailWatcher

                return GmailWatcher(
                    vault_path=str(self.vault_path),
                    credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "config/credentials.json"),
                    token_path=os.getenv("GMAIL_TOKEN_PATH", "config/token.json"),
                    check_interval=int(os.getenv("GMAIL_CHECK_INTERVAL", "120")),
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Gmail", _gmail_factory))

        # Vault Action Watcher (always available)
        def _vault_action_factory():  # noqa: ANN202
            from backend.watchers.vault_action_watcher import VaultActionWatcher

            return VaultActionWatcher(
                vault_path=str(self.vault_path),
                check_interval=5,
            )

        configs.append(("VaultAction", _vault_action_factory))

        # WhatsApp Watcher (local ONLY - requires browser session)
        if self.capabilities.can_watch_whatsapp:
            def _whatsapp_factory():  # noqa: ANN202
                from backend.watchers.whatsapp_watcher import WhatsAppWatcher

                keywords_env = os.getenv("WHATSAPP_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return WhatsAppWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("WHATSAPP_SESSION_PATH", "config/whatsapp_session"),
                    check_interval=int(os.getenv("WHATSAPP_CHECK_INTERVAL", "30")),
                    keywords=keywords,
                    headless=os.getenv("WHATSAPP_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("WhatsApp", _whatsapp_factory))

        # LinkedIn Watcher
        if self.capabilities.can_watch_linkedin:
            def _linkedin_factory():  # noqa: ANN202
                from backend.watchers.linkedin_watcher import LinkedInWatcher

                return LinkedInWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("LINKEDIN_SESSION_PATH", "config/linkedin_session"),
                    check_interval=300,
                    headless=os.getenv("LINKEDIN_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("LinkedIn", _linkedin_factory))

        # Facebook Watcher
        if self.capabilities.can_watch_facebook:
            def _facebook_factory():  # noqa: ANN202
                from backend.watchers.facebook_watcher import FacebookWatcher

                keywords_env = os.getenv("FACEBOOK_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return FacebookWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("FACEBOOK_SESSION_PATH", "config/meta_session"),
                    check_interval=int(os.getenv("FACEBOOK_CHECK_INTERVAL", "120")),
                    keywords=keywords,
                    headless=os.getenv("FACEBOOK_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Facebook", _facebook_factory))

        # Instagram Watcher (local ONLY - requires browser session)
        if self.capabilities.can_watch_instagram if hasattr(self.capabilities, 'can_watch_instagram') else False:
            def _instagram_factory():  # noqa: ANN202
                from backend.watchers.instagram_watcher import InstagramWatcher

                keywords_env = os.getenv("INSTAGRAM_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return InstagramWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("INSTAGRAM_SESSION_PATH", "config/meta_session"),
                    check_interval=int(os.getenv("INSTAGRAM_CHECK_INTERVAL", "60")),
                    keywords=keywords,
                    headless=os.getenv("INSTAGRAM_HEADLESS", "true").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Instagram", _instagram_factory))

        # Twitter Watcher
        if self.capabilities.can_watch_twitter:
            def _twitter_factory():  # noqa: ANN202
                from backend.watchers.twitter_watcher import TwitterWatcher

                keywords_env = os.getenv("TWITTER_KEYWORDS", "")
                keywords = [k.strip() for k in keywords_env.split(",") if k.strip()] or None
                return TwitterWatcher(
                    vault_path=str(self.vault_path),
                    session_path=os.getenv("TWITTER_SESSION_PATH", "config/twitter_session"),
                    check_interval=int(os.getenv("TWITTER_CHECK_INTERVAL", "300")),
                    keywords=keywords,
                    headless=os.getenv("TWITTER_HEADLESS", "false").lower() == "true",
                    dry_run=self.config.dry_run,
                    dev_mode=self.config.dev_mode,
                )

            configs.append(("Twitter", _twitter_factory))

        return configs

    async def run(self) -> None:
        """Main entry point for local orchestrator.

        Extends cloud run() to also start the merge updates loop.
        """
        if not self._acquire_lock():
            logger.error("Cannot start: another orchestrator instance is running")
            return

        try:
            self._started_at = self._now_iso()
            self._log_event("orchestrator_start", "success", f"DEV_MODE={self.config.dev_mode} ZONE=local")

            mode = "DEV_MODE" if self.config.dev_mode else "PRODUCTION"
            logger.info("Starting local orchestrator (%s)", mode)

            # Check content schedule on startup
            await self._check_content_schedule()

            # Check CEO briefing schedule on startup
            await self._check_briefing_schedule()

            # Check for pending Ralph loop tasks
            await self._check_ralph_loops()

            # Start watchers (all enabled for local)
            self._start_watchers()

            # Start action executor
            self._start_action_executor()

            # Start dashboard loop
            self._start_dashboard_loop()

            # Start cloud draft loop (inherited)
            self._start_cloud_draft_loop()

            # Start merge updates loop (local-specific)
            self._start_merge_updates_loop()

            logger.info("Local orchestrator running. Press Ctrl+C to stop.")

            await self._wait_forever()

        finally:
            await self.shutdown()

    def _start_merge_updates_loop(self) -> None:
        """Start the merge updates loop for local orchestrator."""
        self._merge_updates_task = asyncio.create_task(
            self._merge_updates_loop(),
            name="merge-updates-loop",
        )
        logger.info("Started merge updates loop")

    async def _merge_updates_loop(self) -> None:
        """Merge Cloud signals into Dashboard.md.

        This loop:
          1. Reads cloud-generated drafts from Pending_Approval/
          2. Updates Dashboard.md with cloud status
          3. Processes approved items for execution
          4. Syncs WhatsApp and payment states
        """
        from backend.orchestrator.dashboard import (
            DashboardState,
            count_vault_files,
            render_dashboard,
            write_dashboard,
        )

        while True:
            try:
                await self._merge_cloud_signals()
            except Exception:
                logger.exception("Error in merge updates loop")
            await asyncio.sleep(self.config.dashboard_interval)

    async def _merge_cloud_signals(self) -> None:
        """Merge cloud-generated signals into local state.

        - Count pending approvals from cloud
        - Update dashboard with cloud status
        - Process any approved items for execution
        """
        pending_approval = self.vault_path / "Pending_Approval"
        if not pending_approval.exists():
            return

        # Count cloud drafts
        cloud_drafts = list(pending_approval.glob("*.md"))
        if cloud_drafts:
            logger.debug("Found %d pending cloud drafts", len(cloud_drafts))

        # Process approved items
        for draft_file in cloud_drafts:
            try:
                from backend.utils.frontmatter import parse_frontmatter

                fm = parse_frontmatter(draft_file)
                if fm.get("status") == "approved":
                    await self._execute_approved_draft(draft_file)
            except Exception:
                logger.exception("Failed to process draft: %s", draft_file)

    async def _execute_approved_draft(self, draft_file: Path) -> None:
        """Execute an approved draft.

        - Email drafts → send via Gmail
        - Social drafts → post via respective platform
        - Move to Done/ after execution
        """
        from backend.utils.frontmatter import parse_frontmatter

        fm = parse_frontmatter(draft_file)
        draft_type = fm.get("type", "")

        try:
            if draft_type == "email_draft":
                await self._send_email_draft(draft_file, fm)
            elif draft_type == "social_draft":
                await self._post_social_draft(draft_file, fm)
            else:
                logger.warning("Unknown draft type: %s", draft_type)
                return

            # Move to Done
            done_dir = self.vault_path / "Done"
            done_dir.mkdir(parents=True, exist_ok=True)
            draft_file.rename(done_dir / draft_file.name)
            logger.info("Executed draft: %s", draft_file.name)
            self._log_event("draft_executed", "success", draft_file.name)
        except Exception:
            logger.exception("Failed to execute draft: %s", draft_file.name)
            # On error, mark as rejected
            from backend.utils.frontmatter import update_frontmatter
            try:
                update_frontmatter(draft_file, {"status": "rejected", "error": "Execution failed"})
            except Exception:
                pass

    async def _send_email_draft(self, draft_file: Path, frontmatter: dict) -> None:
        """Send email draft via Gmail API."""
        # Implementation would use Gmail API to send
        # For now, just log
        logger.info("Would send email draft: %s", draft_file.name)

    async def _post_social_draft(self, draft_file: Path, frontmatter: dict) -> None:
        """Post social draft to respective platform."""
        # Implementation would use platform API to post
        # For now, just log
        platform = frontmatter.get("platform", "unknown")
        logger.info("Would post to %s: %s", platform, draft_file.name)

    def _acquire_lock(self) -> bool:
        """Acquire orchestrator lock file."""
        from backend.orchestrator.orchestrator import acquire_lock
        return acquire_lock(self.config.lock_file_path)

    async def shutdown(self) -> None:
        """Cancel all tasks including merge updates loop."""
        logger.info("Shutting down local orchestrator...")

        # Cancel merge updates task
        if self._merge_updates_task and not self._merge_updates_task.done():
            self._merge_updates_task.cancel()
            with contextlib.suppress(TimeoutError, asyncio.CancelledError):
                await asyncio.wait_for(self._merge_updates_task, timeout=5.0)

        await super().shutdown()
