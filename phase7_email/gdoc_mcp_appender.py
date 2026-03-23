"""
phase7_email/gdoc_mcp_appender.py
===================================
Phase 7b — Google Doc Appender via MCP.

Appends the combined JSON record to a target Google Doc by spawning the
local Python MCP server (gdocs_mcp_server.py) and calling its
``append_to_google_doc`` tool over stdio.

This module is self-contained and works from:
  • main.py              (CLI / scheduler)
  • api_server.py        (Web UI backend — BackgroundTasks thread)
  • GitHub Actions       (provided token.pickle or GOOGLE_REFRESH_TOKEN
                          is available as a secret)

Append format (per Architecture.md):
    ──── 2026-03-22 ────
    ```json
    { ... combined JSON ... }
    ```

Each pipeline run adds one new dated entry; existing entries are preserved.

Public API
----------
  append_to_gdoc(combined: dict, doc_id: str = "") -> bool
    Appends combined JSON to the target Google Doc via MCP.
    Returns True on success, False on failure (logs the error).
"""

import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# ── Target Google Doc ID ─────────────────────────────────────────────────────
_DEFAULT_GDOC_ID = os.environ.get("GDOC_ID", "")

# Absolute path to the MCP server script (same repo root)
_MCP_SERVER_SCRIPT = str(
    Path(__file__).resolve().parent.parent / "gdocs_mcp_server.py"
)


# ─────────────────────────────────────────────────────────────────────────────
# Formatting helper
# ─────────────────────────────────────────────────────────────────────────────

def _format_entry(combined: dict) -> str:
    """
    Format the combined JSON dict as a dated markdown/text block for appending.

    Format:
        ──── YYYY-MM-DD ────
        ```json
        { ... }
        ```
    """
    date_str = combined.get("date", datetime.now().strftime("%Y-%m-%d"))
    divider = f"\n──── {date_str} ────\n"
    json_block = "```json\n" + json.dumps(combined, indent=2, ensure_ascii=False) + "\n```\n"
    return divider + json_block


# ─────────────────────────────────────────────────────────────────────────────
# Async core — runs the MCP client session
# ─────────────────────────────────────────────────────────────────────────────

async def _append_via_mcp(text: str, doc_id: str) -> bool:
    """
    Spawn gdocs_mcp_server.py as a child process, connect via MCP stdio
    transport, and call its ``append_to_google_doc`` tool.

    Returns True on success, False on any failure.
    """
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        logger.error(
            "[Phase 7b] 'mcp' package not installed. "
            "Run: pip install mcp"
        )
        return False

    server_params = StdioServerParameters(
        command=sys.executable,
        args=[_MCP_SERVER_SCRIPT],
        env=os.environ.copy(),
    )

    try:
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                logger.info("[Phase 7b] Connected to local MCP server.")

                tools_response = await session.list_tools()
                available = [t.name for t in tools_response.tools]
                logger.info("[Phase 7b] MCP tools available: %s", available)

                target_tool = "append_to_google_doc"
                if target_tool not in available:
                    logger.error(
                        "[Phase 7b] Tool '%s' not found on MCP server. "
                        "Available: %s",
                        target_tool, available,
                    )
                    return False

                logger.info(
                    "[Phase 7b] Calling '%s' for doc_id=%s …",
                    target_tool, doc_id,
                )
                result = await session.call_tool(
                    target_tool,
                    arguments={"doc_id": doc_id, "text": text},
                )
                result_text = str(result)
                logger.info("[Phase 7b] MCP result: %s", result_text)

                # The server returns "✅ Successfully …" on success
                if "successfully" in result_text.lower() or "✅" in result_text:
                    return True
                else:
                    logger.error("[Phase 7b] MCP reported failure: %s", result_text)
                    return False

    except Exception as exc:
        logger.error("[Phase 7b] MCP session error: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Main public function
# ─────────────────────────────────────────────────────────────────────────────

def append_to_gdoc(combined: dict, doc_id: str = "") -> bool:
    """
    Append the combined JSON record to a Google Doc using the local MCP server.

    This function is safe to call from any context:
      - synchronous scripts  (main.py, GitHub Actions)
      - FastAPI BackgroundTasks thread (api_server.py)

    It creates a new asyncio event loop if one is not already running.

    Parameters
    ----------
    combined : dict — output of json_assembler.build_combined_json()
    doc_id   : str  — Google Doc ID (overrides GDOC_ID env var if provided)

    Returns
    -------
    bool — True if the append succeeded, False otherwise.
    """
    target_doc_id = doc_id or os.environ.get("GDOC_ID", "") or _DEFAULT_GDOC_ID

    if not target_doc_id:
        logger.warning(
            "[Phase 7b] GDOC_ID not set. Skipping Google Doc append. "
            "Set the GDOC_ID environment variable to enable this feature."
        )
        return False

    entry_text = _format_entry(combined)
    logger.info(
        "[Phase 7b] Appending combined JSON for date=%s to Google Doc ID=%s.",
        combined.get("date", "?"),
        target_doc_id,
    )

    # Run the async MCP call, handling both top-level and nested event loops
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We are inside an existing event loop (e.g. FastAPI async context).
            # Use a fresh thread-based approach to avoid "cannot run nested" error.
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(
                    asyncio.run,
                    _append_via_mcp(entry_text, target_doc_id),
                )
                return future.result(timeout=120)
        else:
            return loop.run_until_complete(
                _append_via_mcp(entry_text, target_doc_id)
            )
    except RuntimeError:
        # Fallback: create a brand new event loop
        return asyncio.run(_append_via_mcp(entry_text, target_doc_id))
    except Exception as exc:
        logger.error("[Phase 7b] Failed to append to Google Doc via MCP: %s", exc)
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Standalone execution (for testing the formatter)
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    sample = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "weekly_pulse": {
            "themes": ["UI Issues", "Performance", "Fee Confusion"],
            "quotes": ["App crashes on login.", "Why is exit load so high?", "Support is slow."],
            "action_ideas": ["Fix login crash", "Add fee explainer tab", "Improve support SLA"],
        },
        "fee_scenario": "Mutual Fund Exit Load",
        "explanation_bullets": [
            "Exit load is a redemption fee charged when units are sold early.",
            "Rates vary by fund house and holding period.",
            "Terms are disclosed in the fund's Scheme Information Document (SID).",
        ],
        "source_links": [
            "https://groww.in/p/exit-load-in-mutual-funds",
            "https://mf.nipponindiaim.com/investoreducation/financial-term-of-the-week-exit-load",
        ],
        "last_checked": datetime.now().strftime("%Y-%m-%d"),
    }
    print(_format_entry(sample))
