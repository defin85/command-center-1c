#!/usr/bin/env python3
"""
Chrome DevTools Protocol (CDP) utility for debugging frontend.

Usage:
    ./scripts/dev/chrome-debug.py console          # Get console errors/warnings
    ./scripts/dev/chrome-debug.py screenshot       # Take screenshot
    ./scripts/dev/chrome-debug.py eval "js code"   # Execute JS and print result
    ./scripts/dev/chrome-debug.py reload           # Reload page
    ./scripts/dev/chrome-debug.py pages            # List open pages
    ./scripts/dev/chrome-debug.py network          # Capture network requests (3 sec)

Requirements:
    pip install websockets

Before use:
    chromium --remote-debugging-port=9222 --no-first-run &
"""

import argparse
import asyncio
import base64
import json
import sys
from datetime import datetime
from pathlib import Path
from urllib.request import urlopen

CDP_URL = "http://127.0.0.1:9222"
DEFAULT_PAGE_URL = "localhost:5173"


def get_pages() -> list[dict]:
    """Get list of browser pages."""
    try:
        with urlopen(f"{CDP_URL}/json", timeout=2) as resp:
            return json.loads(resp.read())
    except Exception:
        print(f"Error: Cannot connect to Chrome at {CDP_URL}")
        print("Make sure Chromium is running with: chromium --remote-debugging-port=9222 --no-first-run &")
        sys.exit(1)


def find_page(url_pattern: str = DEFAULT_PAGE_URL) -> dict | None:
    """Find page by URL pattern."""
    pages = get_pages()
    for page in pages:
        if url_pattern in page.get("url", "") and page.get("type") == "page":
            return page
    return None


async def cdp_command(ws_url: str, method: str, params: dict = None) -> dict:
    """Execute single CDP command."""
    import websockets

    async with websockets.connect(ws_url) as ws:
        msg = {"id": 1, "method": method}
        if params:
            msg["params"] = params
        await ws.send(json.dumps(msg))
        return json.loads(await ws.recv())


async def get_console_messages(ws_url: str, timeout: float = 3.0) -> list[dict]:
    """Capture console messages after page reload."""
    import websockets

    messages = []
    async with websockets.connect(ws_url) as ws:
        # Enable Runtime and Page
        await ws.send(json.dumps({"id": 1, "method": "Runtime.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        await ws.recv()

        # Reload page to capture fresh messages
        await ws.send(json.dumps({"id": 3, "method": "Page.reload"}))

        # Collect messages
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                data = json.loads(msg)
                if data.get("method") == "Runtime.consoleAPICalled":
                    params = data["params"]
                    level = params["type"]
                    args = []
                    for arg in params.get("args", []):
                        if "value" in arg:
                            args.append(str(arg["value"]))
                        elif "description" in arg:
                            args.append(arg["description"])
                    messages.append({
                        "level": level,
                        "message": " ".join(args)
                    })
        except asyncio.TimeoutError:
            pass

    return messages


async def capture_network(ws_url: str, timeout: float = 3.0) -> list[dict]:
    """Capture network requests after page reload."""
    import websockets

    requests = []
    async with websockets.connect(ws_url) as ws:
        # Enable Network and Page
        await ws.send(json.dumps({"id": 1, "method": "Network.enable"}))
        await ws.recv()
        await ws.send(json.dumps({"id": 2, "method": "Page.enable"}))
        await ws.recv()

        # Reload page
        await ws.send(json.dumps({"id": 3, "method": "Page.reload"}))

        # Collect requests
        try:
            while True:
                msg = await asyncio.wait_for(ws.recv(), timeout=timeout)
                data = json.loads(msg)
                if data.get("method") == "Network.requestWillBeSent":
                    req = data["params"]["request"]
                    requests.append({
                        "method": req["method"],
                        "url": req["url"]
                    })
                elif data.get("method") == "Network.responseReceived":
                    resp = data["params"]["response"]
                    # Update request with status
                    for r in requests:
                        if r["url"] == resp["url"]:
                            r["status"] = resp["status"]
                            break
        except asyncio.TimeoutError:
            pass

    return requests


def cmd_pages(args):
    """List browser pages."""
    pages = get_pages()
    for i, page in enumerate(pages):
        if page.get("type") == "page":
            print(f"{i}: [{page.get('type')}] {page.get('title', 'No title')}")
            print(f"   URL: {page.get('url')}")
            print(f"   ID: {page.get('id')}")
            print()


def cmd_console(args):
    """Get console errors and warnings."""
    page = find_page(args.url)
    if not page:
        print(f"Error: No page found matching '{args.url}'")
        sys.exit(1)

    print(f"Capturing console from: {page['url']}")
    print(f"Reloading page and waiting {args.timeout}s for messages...\n")

    messages = asyncio.run(get_console_messages(
        page["webSocketDebuggerUrl"],
        timeout=args.timeout
    ))

    # Filter by level
    if args.errors_only:
        messages = [m for m in messages if m["level"] in ("error", "warning")]

    if not messages:
        print("No console messages found.")
        return

    # Group by level
    errors = [m for m in messages if m["level"] == "error"]
    warnings = [m for m in messages if m["level"] == "warning"]
    logs = [m for m in messages if m["level"] not in ("error", "warning")]

    if errors:
        print(f"ERRORS ({len(errors)}):")
        for m in errors:
            print(f"  {m['message'][:200]}")
        print()

    if warnings:
        print(f"WARNINGS ({len(warnings)}):")
        for m in warnings:
            print(f"  {m['message'][:200]}")
        print()

    if logs and not args.errors_only:
        print(f"LOGS ({len(logs)}):")
        for m in logs[:10]:  # Limit logs
            print(f"  [{m['level']}] {m['message'][:100]}")
        if len(logs) > 10:
            print(f"  ... and {len(logs) - 10} more")


def cmd_screenshot(args):
    """Take screenshot of the page."""
    page = find_page(args.url)
    if not page:
        print(f"Error: No page found matching '{args.url}'")
        sys.exit(1)

    result = asyncio.run(cdp_command(
        page["webSocketDebuggerUrl"],
        "Page.captureScreenshot",
        {"format": "png"}
    ))

    if "result" not in result:
        print(f"Error: {result}")
        sys.exit(1)

    output = Path(args.output)
    output.write_bytes(base64.b64decode(result["result"]["data"]))
    print(f"Screenshot saved: {output}")


def cmd_eval(args):
    """Execute JavaScript and print result."""
    page = find_page(args.url)
    if not page:
        print(f"Error: No page found matching '{args.url}'")
        sys.exit(1)

    result = asyncio.run(cdp_command(
        page["webSocketDebuggerUrl"],
        "Runtime.evaluate",
        {"expression": args.code, "returnByValue": True}
    ))

    if "result" in result:
        value = result["result"].get("result", {})
        if "value" in value:
            print(value["value"])
        elif "description" in value:
            print(value["description"])
        else:
            print(json.dumps(value, indent=2))
    else:
        print(f"Error: {result}")


def cmd_reload(args):
    """Reload the page."""
    page = find_page(args.url)
    if not page:
        print(f"Error: No page found matching '{args.url}'")
        sys.exit(1)

    asyncio.run(cdp_command(
        page["webSocketDebuggerUrl"],
        "Page.reload",
        {"ignoreCache": args.hard}
    ))
    print(f"Reloaded: {page['url']}")


def cmd_network(args):
    """Capture network requests."""
    page = find_page(args.url)
    if not page:
        print(f"Error: No page found matching '{args.url}'")
        sys.exit(1)

    print(f"Capturing network from: {page['url']}")
    print(f"Reloading page and waiting {args.timeout}s...\n")

    requests = asyncio.run(capture_network(
        page["webSocketDebuggerUrl"],
        timeout=args.timeout
    ))

    if not requests:
        print("No network requests captured.")
        return

    # Filter API requests
    if args.api_only:
        requests = [r for r in requests if "/api/" in r["url"]]

    # Show failed requests
    failed = [r for r in requests if r.get("status", 200) >= 400]
    if failed:
        print(f"FAILED REQUESTS ({len(failed)}):")
        for r in failed:
            print(f"  [{r.get('status', '?')}] {r['method']} {r['url']}")
        print()

    # Show all requests
    print(f"ALL REQUESTS ({len(requests)}):")
    for r in requests[:20]:
        status = r.get("status", "...")
        print(f"  [{status}] {r['method']} {r['url'][:80]}")
    if len(requests) > 20:
        print(f"  ... and {len(requests) - 20} more")


def main():
    parser = argparse.ArgumentParser(
        description="Chrome DevTools Protocol utility",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        "--url", "-u",
        default=DEFAULT_PAGE_URL,
        help=f"Page URL pattern to find (default: {DEFAULT_PAGE_URL})"
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # pages
    subparsers.add_parser("pages", help="List open browser pages")

    # console
    p_console = subparsers.add_parser("console", help="Get console messages")
    p_console.add_argument("--timeout", "-t", type=float, default=3.0)
    p_console.add_argument("--errors-only", "-e", action="store_true")

    # screenshot
    p_screenshot = subparsers.add_parser("screenshot", help="Take screenshot")
    p_screenshot.add_argument(
        "--output", "-o",
        default=f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
    )

    # eval
    p_eval = subparsers.add_parser("eval", help="Execute JavaScript")
    p_eval.add_argument("code", help="JavaScript code to execute")

    # reload
    p_reload = subparsers.add_parser("reload", help="Reload the page")
    p_reload.add_argument("--hard", action="store_true", help="Ignore cache")

    # network
    p_network = subparsers.add_parser("network", help="Capture network requests")
    p_network.add_argument("--timeout", "-t", type=float, default=3.0)
    p_network.add_argument("--api-only", "-a", action="store_true")

    args = parser.parse_args()

    commands = {
        "pages": cmd_pages,
        "console": cmd_console,
        "screenshot": cmd_screenshot,
        "eval": cmd_eval,
        "reload": cmd_reload,
        "network": cmd_network,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()
