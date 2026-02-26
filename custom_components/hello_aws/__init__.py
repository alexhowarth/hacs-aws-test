"""Hello AWS IoT - minimal integration to verify HACS installs awsiotsdk + awscrt."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta
from pathlib import Path

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor"]

UPDATE_ENTITY_ID = "update.hello_aws_iot_update"
UPDATE_CHECK_INTERVAL = timedelta(minutes=1)

# TODO: See TODO.md — this polling loop is proof-of-concept only.
# In production the update trigger will be a push, not a poll.
GITHUB_REPO = "alexhowarth/hacs-aws-test"
GITHUB_RELEASES_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"

# Read our own version once at import time (runs on ImportExecutor, off event loop)
_MANIFEST = json.loads((Path(__file__).parent / "manifest.json").read_text())
INTEGRATION_VERSION = _MANIFEST.get("version", "unknown")


async def _get_latest_github_version(hass: HomeAssistant) -> str | None:
    """Return the latest release version from GitHub (no 'v' prefix), or None on error."""
    session = async_get_clientsession(hass)
    try:
        async with session.get(GITHUB_RELEASES_URL) as resp:
            if resp.status == 200:
                data = await resp.json(content_type=None)
                tag = data.get("tag_name", "")
                return tag.lstrip("v")
            _LOGGER.warning(
                "[hello_aws v%s] GitHub API returned HTTP %s", INTEGRATION_VERSION, resp.status
            )
    except Exception as err:
        _LOGGER.warning("[hello_aws v%s] GitHub API error: %s", INTEGRATION_VERSION, err)
    return None


async def _force_hacs_refresh(hass: HomeAssistant) -> bool:
    """Call HACS internals to force a GitHub metadata refresh for our repository.

    Mirrors what the 'hacs/repository/refresh' WebSocket handler does, but
    called directly so we don't need a WebSocket connection.
    Returns True if the refresh succeeded.
    """
    hacs = hass.data.get("hacs")
    if hacs is None:
        _LOGGER.warning("[hello_aws v%s] HACS not found in hass.data — is HACS installed?", INTEGRATION_VERSION)
        return False
    try:
        repo = hacs.repositories.get_by_full_name(GITHUB_REPO)
        if repo is None:
            _LOGGER.warning("[hello_aws v%s] HACS has no record of repo %s", INTEGRATION_VERSION, GITHUB_REPO)
            return False
        _LOGGER.debug("[hello_aws v%s] Forcing HACS repository refresh for %s...", INTEGRATION_VERSION, GITHUB_REPO)
        await repo.update_repository(ignore_issues=True, force=True)
        await hacs.data.async_write()
        hacs.coordinators[repo.data.category].async_update_listeners()
        _LOGGER.debug("[hello_aws v%s] HACS repository refresh complete.", INTEGRATION_VERSION)
        return True
    except Exception as err:
        _LOGGER.warning("[hello_aws v%s] HACS refresh failed: %s", INTEGRATION_VERSION, err)
        return False


async def _refresh_and_install(hass: HomeAssistant, now=None) -> None:
    """Query GitHub directly for latest version; if newer, force HACS to refresh then install."""
    _LOGGER.debug("[hello_aws v%s] Querying GitHub releases API...", INTEGRATION_VERSION)

    latest = await _get_latest_github_version(hass)
    if latest is None:
        return  # warning already logged inside _get_latest_github_version

    _LOGGER.info(
        "[hello_aws v%s] GitHub: latest=v%s  running=v%s",
        INTEGRATION_VERSION, latest, INTEGRATION_VERSION,
    )

    if latest == INTEGRATION_VERSION:
        _LOGGER.debug("[hello_aws v%s] Up to date.", INTEGRATION_VERSION)
        return

    # Newer version on GitHub — force HACS to re-fetch metadata from GitHub.
    _LOGGER.warning(
        "[hello_aws v%s] Update available: v%s → v%s. Forcing HACS metadata refresh...",
        INTEGRATION_VERSION, INTEGRATION_VERSION, latest,
    )
    await _force_hacs_refresh(hass)

    # Ask HA to update the entity state from HACS's (now-fresh) cache.
    try:
        await hass.services.async_call(
            "homeassistant", "update_entity",
            {"entity_id": UPDATE_ENTITY_ID}, blocking=True,
        )
    except Exception as err:
        _LOGGER.warning("[hello_aws v%s] update_entity failed: %s", INTEGRATION_VERSION, err)
        return

    state = hass.states.get(UPDATE_ENTITY_ID)
    hacs_installed = state.attributes.get("installed_version") if state else None
    hacs_latest = state.attributes.get("latest_version") if state else None
    _LOGGER.info(
        "[hello_aws v%s] HACS entity after forced refresh: state=%s installed=%s latest=%s",
        INTEGRATION_VERSION,
        state.state if state else "NOT_FOUND",
        hacs_installed,
        hacs_latest,
    )

    # HACS has already written v<latest> to disk (installed == latest) but HA's
    # integration cache layer means async_reload always re-serves the old module
    # from memory — even importlib.reload can't clear HA's Integration object cache.
    # The only reliable way to pick up new code is a full HA restart.
    if hacs_installed and hacs_installed.lstrip("v") == latest:
        _LOGGER.warning(
            "[hello_aws v%s] v%s is on disk. Restarting HA to load new code...",
            INTEGRATION_VERSION, latest,
        )
        await hass.services.async_call("homeassistant", "restart", blocking=False)
        return

    if state and state.state == "on":
        _LOGGER.warning("[hello_aws v%s] Triggering HACS install of %s...", INTEGRATION_VERSION, hacs_latest)
        await hass.services.async_call(
            "update", "install",
            {"entity_id": UPDATE_ENTITY_ID}, blocking=False,
        )
    else:
        _LOGGER.warning(
            "[hello_aws v%s] HACS entity not ready (state=%s) — will retry next interval.",
            INTEGRATION_VERSION, state.state if state else "NOT_FOUND",
        )


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Hello AWS IoT from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    # --- The whole point: import the SDK and prove it loaded ---
    try:
        import awscrt  # noqa: F811
        import awsiot  # noqa: F811

        hass.data[DOMAIN][entry.entry_id] = {
            "awscrt_version": getattr(awscrt, "__version__", "unknown"),
            "awsiot_version": getattr(awsiot, "__version__", "unknown"),
        }
        _LOGGER.info(
            "awscrt %s and awsiot %s loaded successfully",
            hass.data[DOMAIN][entry.entry_id]["awscrt_version"],
            hass.data[DOMAIN][entry.entry_id]["awsiot_version"],
        )
    except ImportError as err:
        _LOGGER.error("Failed to import AWS IoT SDK: %s", err)
        hass.data[DOMAIN][entry.entry_id] = {
            "awscrt_version": f"IMPORT FAILED: {err}",
            "awsiot_version": f"IMPORT FAILED: {err}",
        }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    _LOGGER.info("[hello_aws v%s] Integration loaded. Scheduling update checks.", INTEGRATION_VERSION)

    # Run first check after 30s (let HA + HACS finish initialising), then every minute.
    async def _initial_check(_=None):
        _LOGGER.info("[hello_aws v%s] Initial update check starting (30s delay)...", INTEGRATION_VERSION)
        await asyncio.sleep(30)
        await _refresh_and_install(hass)

    entry.async_create_background_task(hass, _initial_check(), "hello_aws_initial_update_check")

    async def _scheduled_check(now=None) -> None:
        _LOGGER.info("[hello_aws v%s] Scheduled update check fired at %s", INTEGRATION_VERSION, now)
        await _refresh_and_install(hass, now)

    cancel_interval = async_track_time_interval(
        hass, _scheduled_check, UPDATE_CHECK_INTERVAL
    )
    hass.data[DOMAIN][f"{entry.entry_id}_cancel_update"] = cancel_interval

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    # Cancel the periodic update check
    cancel = hass.data[DOMAIN].pop(f"{entry.entry_id}_cancel_update", None)
    if cancel:
        cancel()

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
