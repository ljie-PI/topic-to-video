#!/usr/bin/env python3
"""Gemini Deep Research automation via Playwright over CDP.

Submits a research prompt to Google Gemini's Deep Research feature and waits
for the full report.  Browser model: attaches over CDP (default
http://localhost:9222) to a Chrome process.  If no CDP responder is reachable,
auto-launches system Chrome with --user-data-dir=<profile-dir>.  Profile
defaults to ./chrome_profile and is SHARED with other
tools (harvest-pages, etc.).  Chrome is left running on exit so subsequent
invocations reconnect instantly.

Usage:
  python3 gemini-deep-research.py \\
    --prompt "Comprehensive overview of quantum computing" \\
    --output-dir ./quantum_computing/

Output convention:
  stdout : single JSON object
    success: {"success": true, "report_path": "...", "sources_path": "...",
              "report_length": N, "source_count": N}
    error:   {"success": false, "error": "...", "failed_step": N}
  stderr : human-readable progress prefixed with `[gemini-deep-research]`
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

TOOL_NAME = 'gemini-deep-research'
DEFAULT_CDP_URL = 'http://localhost:9222'
DEFAULT_PROFILE_DIR = './chrome_profile'
CHROME_CANDIDATES_LINUX = [
    '/usr/bin/google-chrome',
    '/usr/bin/google-chrome-stable',
    '/usr/bin/chromium',
    '/usr/bin/chromium-browser',
]
CHROME_CANDIDATES_MAC = [
    '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
    '/Applications/Chromium.app/Contents/MacOS/Chromium',
    '/Applications/Google Chrome Canary.app/Contents/MacOS/Google Chrome Canary',
]
CHROME_CANDIDATES_WIN = [
    os.path.expandvars(r'%ProgramFiles%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%ProgramFiles(x86)%\Google\Chrome\Application\chrome.exe'),
    os.path.expandvars(r'%LocalAppData%\Google\Chrome\Application\chrome.exe'),
]
CDP_READY_TIMEOUT_S = 15.0
CDP_POLL_INTERVAL_S = 0.5

GEMINI_URL = 'https://gemini.google.com/app'

SEL = {
    'input_box': "//div[contains(@class,'ql-editor') and @role='textbox']",
    'send_button': "//button[contains(@class,'send-button')]",
    'tools_button': "//button[contains(@class,'toolbox-drawer-button')]",
    'tool_menu': "//mat-action-list[@id='toolbox-drawer-menu']",
    'deep_research_item': "//mat-action-list[@id='toolbox-drawer-menu']//button[.//div[contains(text(),'Deep Research')]]",
    'confirm_button': "//button[@data-test-id='confirm-button']",
    'last_message': "(//message-content)[last()]",
    'last_sources': "(//message-content)[last()]//sources-carousel-inline",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

class ArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        log(f'Argument error: {message}')
        print(json.dumps({'success': False, 'error': message}, ensure_ascii=False))
        self.exit(2)


def log(message: str) -> None:
    print(f'[{TOOL_NAME}] {message}', file=sys.stderr)


def fail(message: str, exit_code: int = 1, failed_step: Optional[int] = None) -> None:
    log(message)
    obj: Dict[str, Any] = {'success': False, 'error': message}
    if failed_step is not None:
        obj['failed_step'] = failed_step
    print(json.dumps(obj, ensure_ascii=False))
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    p = ArgumentParser(description='Gemini Deep Research automation (Playwright over CDP).')
    p.add_argument('--prompt', required=True, help='Research prompt to submit to Gemini Deep Research.')
    p.add_argument('--output-dir', required=True, help='Directory for report and sources output files.')
    p.add_argument('--cdp-url', default=DEFAULT_CDP_URL,
                   help=f'CDP endpoint (default {DEFAULT_CDP_URL}).')
    p.add_argument('--profile-dir', default=DEFAULT_PROFILE_DIR,
                   help=f'Chrome profile dir (default {DEFAULT_PROFILE_DIR}).')
    p.add_argument('--chrome-path', default=None,
                   help='Path to Chrome executable. Auto-detected if unset.')
    p.add_argument('--headless', default='auto', choices=('auto', 'on', 'off'),
                   help="Chrome headless mode. 'auto' (default) = headless when DISPLAY is unset.")
    p.add_argument('--no-sandbox', action='store_true', default=None,
                   help='Pass --no-sandbox to Chrome (auto-enabled when running as root or inside a container).')
    p.add_argument('--timeout', type=int, default=600,
                   help='Timeout in seconds for deep research completion (default 600).')
    p.add_argument('--start-from-step', type=int, default=1, choices=range(1, 11),
                   metavar='[1-10]',
                   help='Resume from a specific step (1-10, default 1).')
    p.add_argument('--page-url', default=None,
                   help='Existing Gemini conversation URL to resume from.')
    return p.parse_args()


# ---------------------------------------------------------------------------
# CDP / browser setup  (mirrors harvest-pages.py)
# ---------------------------------------------------------------------------

def _chrome_candidates() -> list:
    """Return Chrome candidate paths for the current platform."""
    import platform
    s = platform.system()
    if s == 'Darwin':
        return CHROME_CANDIDATES_MAC
    elif s == 'Windows':
        return CHROME_CANDIDATES_WIN
    return CHROME_CANDIDATES_LINUX


def find_chrome(explicit: Optional[str]) -> Optional[str]:
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_path = os.environ.get('CHROME_PATH')
    if env_path and Path(env_path).is_file():
        return env_path
    for cand in _chrome_candidates():
        if Path(cand).is_file():
            return cand
    return None


def cdp_ready(cdp_url: str) -> bool:
    from urllib import request as urlrequest
    from urllib import error as urlerror
    try:
        with urlrequest.urlopen(f'{cdp_url.rstrip("/")}/json/version', timeout=2.0) as resp:
            return resp.status == 200
    except (urlerror.URLError, urlerror.HTTPError, TimeoutError, ConnectionError, OSError):
        return False


def _should_be_headless(headless_mode: str) -> bool:
    if headless_mode == 'on':
        return True
    if headless_mode == 'off':
        return False
    return not os.environ.get('DISPLAY')


def _should_disable_sandbox(no_sandbox_flag: Optional[bool]) -> bool:
    if no_sandbox_flag:
        return True
    try:
        if os.geteuid() == 0:
            return True
    except AttributeError:
        pass
    return Path('/.dockerenv').exists()


def launch_chrome(chrome_path: str, cdp_url: str, profile_dir: Path,
                  headless_mode: str = 'auto',
                  no_sandbox_flag: Optional[bool] = None) -> subprocess.Popen:
    parsed = urlparse(cdp_url)
    port = parsed.port or 9222
    profile_dir.mkdir(parents=True, exist_ok=True)
    args = [
        chrome_path,
        f'--remote-debugging-port={port}',
        f'--user-data-dir={profile_dir}',
        '--no-first-run',
        '--no-default-browser-check',
        '--disable-features=Translate',
    ]
    if _should_be_headless(headless_mode):
        args.append('--headless=new')
        args.append('--disable-gpu')
    if _should_disable_sandbox(no_sandbox_flag):
        args.append('--no-sandbox')
    log(f'Launching Chrome: {chrome_path} (port={port}, profile={profile_dir}, '
        f'flags={[a for a in args[3:] if a.startswith("--")]})')
    return subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
    )


def wait_for_cdp(cdp_url: str, proc: Optional[subprocess.Popen],
                 profile_dir: Optional[Path] = None) -> None:
    deadline = time.time() + CDP_READY_TIMEOUT_S
    while time.time() < deadline:
        if proc is not None and proc.poll() is not None:
            profile_msg = str(profile_dir) if profile_dir else DEFAULT_PROFILE_DIR
            fail(
                f'Chrome exited immediately (code {proc.returncode}). '
                'Profile may be locked by another Chrome window. '
                f'Profile path: {profile_msg}. '
                'Close other Chrome instances using this profile, or pass a different --profile-dir.'
            )
        if cdp_ready(cdp_url):
            return
        time.sleep(CDP_POLL_INTERVAL_S)
    fail(
        f'CDP at {cdp_url} did not become ready within {CDP_READY_TIMEOUT_S}s. '
        'Check that the port is free and Chrome can launch with the given profile.'
    )


def ensure_cdp(args: argparse.Namespace) -> None:
    """Ensure something is listening on CDP. Auto-launch system Chrome if not."""
    if cdp_ready(args.cdp_url):
        log(f'CDP already ready at {args.cdp_url}; reusing existing Chrome')
        return
    chrome_path = find_chrome(args.chrome_path)
    if not chrome_path:
        fail(
            'System Chrome not found. Tried: '
            f'{", ".join(_chrome_candidates())}. '
            'Install Chrome or pass --chrome-path.'
        )
    profile_dir = Path(args.profile_dir).expanduser()
    proc = launch_chrome(chrome_path, args.cdp_url, profile_dir,
                         headless_mode=args.headless,
                         no_sandbox_flag=args.no_sandbox)
    wait_for_cdp(args.cdp_url, proc, profile_dir)
    log(f'CDP ready at {args.cdp_url} (chrome pid={proc.pid}; left running on exit)')


# ---------------------------------------------------------------------------
# HTML-to-Markdown conversion
# ---------------------------------------------------------------------------

def html_to_markdown(page: Any, container_handle: Any) -> str:
    """Convert an element's children to Markdown by traversing in the browser."""
    md = page.evaluate('''(container) => {
        function escMd(t) { return t; }
        function inlineText(el) {
            let out = '';
            for (const n of el.childNodes) {
                if (n.nodeType === 3) { out += n.textContent; continue; }
                if (n.nodeType !== 1) continue;
                const tag = n.tagName;
                if (tag === 'B' || tag === 'STRONG') { out += '**' + inlineText(n) + '**'; }
                else if (tag === 'I' || tag === 'EM') { out += '*' + inlineText(n) + '*'; }
                else if (tag === 'CODE') { out += '`' + n.textContent + '`'; }
                else if (tag === 'A') { out += '[' + inlineText(n) + '](' + (n.href || '') + ')'; }
                else if (tag === 'BR') { out += '\\n'; }
                else { out += inlineText(n); }
            }
            return out;
        }
        function convertNode(el) {
            const tag = el.tagName;
            if (!tag) return el.textContent || '';
            if (/^H[1-6]$/.test(tag)) {
                const level = parseInt(tag[1]);
                return '#'.repeat(level) + ' ' + inlineText(el) + '\\n\\n';
            }
            if (tag === 'P') return inlineText(el) + '\\n\\n';
            if (tag === 'UL') {
                return Array.from(el.children).map(li => '- ' + inlineText(li)).join('\\n') + '\\n\\n';
            }
            if (tag === 'OL') {
                return Array.from(el.children).map((li, i) => (i+1) + '. ' + inlineText(li)).join('\\n') + '\\n\\n';
            }
            if (tag === 'TABLE') {
                const rows = Array.from(el.querySelectorAll('tr'));
                if (rows.length === 0) return '';
                const matrix = rows.map(r =>
                    Array.from(r.querySelectorAll('th, td')).map(c => inlineText(c).trim())
                );
                const hdr = matrix[0];
                let md = '| ' + hdr.join(' | ') + ' |\\n';
                md += '| ' + hdr.map(() => '---').join(' | ') + ' |\\n';
                for (let i = 1; i < matrix.length; i++) {
                    md += '| ' + matrix[i].join(' | ') + ' |\\n';
                }
                return md + '\\n';
            }
            if (tag === 'PRE') return '```\\n' + el.textContent + '\\n```\\n\\n';
            if (tag === 'BLOCKQUOTE') {
                return el.textContent.split('\\n').map(l => '> ' + l).join('\\n') + '\\n\\n';
            }
            // Recurse for divs and other containers
            let out = '';
            for (const child of el.children) { out += convertNode(child); }
            return out || (inlineText(el) + '\\n\\n');
        }
        // Look for .markdown child first, fall back to container itself
        const target = container.querySelector('.markdown') || container;
        let result = '';
        for (const child of target.children) { result += convertNode(child); }
        return result.trim() || target.textContent || '';
    }''', container_handle)
    return md


# ---------------------------------------------------------------------------
# Source extraction
# ---------------------------------------------------------------------------

def extract_sources(page: Any) -> List[Dict[str, str]]:
    """Extract sources by clicking each carousel expand button one-by-one.

    Gemini renders each inline citation as a collapsed ``sources-carousel-inline``
    with a "了解详情" expand button.  Only one carousel is visible at a time, so
    we must click each button, wait for the carousel to render, scrape the
    ``default-source-card`` links, then move on to the next.
    """
    total = page.evaluate('''() => {
        const lastMsg = document.evaluate(
            "(//message-content)[last()]",
            document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
        ).singleNodeValue;
        return lastMsg
            ? lastMsg.querySelectorAll("sources-carousel-inline").length
            : 0;
    }''')
    if total == 0:
        return []

    log(f'Found {total} citation carousels — clicking each to extract sources...')
    seen: set = set()
    result: List[Dict[str, str]] = []

    for i in range(total):
        # Scroll the button into view and click it
        page.evaluate(f'''() => {{
            const lastMsg = document.evaluate(
                "(//message-content)[last()]",
                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;
            const inlines = lastMsg.querySelectorAll("sources-carousel-inline");
            const btn = inlines[{i}].querySelector("button");
            if (btn) {{
                btn.scrollIntoView({{behavior: "instant", block: "center"}});
                btn.click();
            }}
        }}''')
        page.wait_for_timeout(1200)

        # Scrape visible source cards
        sources = page.evaluate('''() => {
            const lastMsg = document.evaluate(
                "(//message-content)[last()]",
                document, null, XPathResult.FIRST_ORDERED_NODE_TYPE, null
            ).singleNodeValue;
            if (!lastMsg) return [];
            const out = [];
            for (const a of lastMsg.querySelectorAll("default-source-card a[href]")) {
                const carousel = a.closest("sources-carousel");
                if (!carousel) continue;
                const style = getComputedStyle(carousel);
                if (style.visibility === "hidden" || style.display === "none") continue;
                out.push({title: (a.textContent || "").trim(), url: a.href});
            }
            return out;
        }''')

        for s in (sources or []):
            url = s.get('url', '')
            if url and url not in seen:
                seen.add(url)
                result.append(s)

    log(f'Extracted {len(result)} unique sources from {total} carousels')
    return result


# ---------------------------------------------------------------------------
# Main automation flow
# ---------------------------------------------------------------------------

def run(args: argparse.Namespace) -> None:
    from playwright.sync_api import sync_playwright

    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    start = args.start_from_step

    with sync_playwright() as pw:
        # Step 1: Connect to Chrome via CDP (always ensure CDP is ready)
        log('Step 1: Connecting to Chrome via CDP...')
        try:
            ensure_cdp(args)
        except SystemExit:
            raise
        except Exception as e:
            fail(f'Step 1 failed: could not connect to Chrome: {e}', failed_step=1)

        try:
            browser = pw.chromium.connect_over_cdp(args.cdp_url)
        except Exception as e:
            fail(f'Step 1 failed: CDP connect error: {e}', failed_step=1)

        # Use first context / first page, or create new
        if browser.contexts:
            context = browser.contexts[0]
            page = context.pages[0] if context.pages else context.new_page()
        else:
            context = browser.new_context()
            page = context.new_page()

        # Step 2: Navigate
        if start <= 2:
            nav_url = args.page_url if args.page_url else GEMINI_URL
            log(f'Step 2: Navigating to {nav_url}...')
            try:
                page.goto(nav_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                fail(f'Step 2 failed: navigation error: {e}', failed_step=2)
        elif args.page_url:
            log('Step 2: Navigating to provided page URL...')
            try:
                page.goto(args.page_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                fail(f'Step 2 failed: navigation error: {e}', failed_step=2)

        # Step 3: Verify login
        if start <= 3:
            log('Step 3: Verifying Gemini login...')
            try:
                page.wait_for_selector(f'xpath={SEL["input_box"]}', timeout=30000)
            except Exception:
                fail('Step 3 failed: Not logged in to Gemini. Please log in manually first.', failed_step=3)

        # Step 4: Activate Deep Research mode
        if start <= 4:
            log('Step 4: Activating Deep Research mode...')
            try:
                page.locator(f'xpath={SEL["tools_button"]}').click()
                page.wait_for_selector(f'xpath={SEL["tool_menu"]}', timeout=10000)
                page.locator(f'xpath={SEL["deep_research_item"]}').click()
                page.wait_for_timeout(1500)
            except Exception as e:
                fail(f'Step 4 failed: could not activate Deep Research: {e}', failed_step=4)

        # Step 5: Type the research prompt
        if start <= 5:
            log('Step 5: Typing research prompt...')
            try:
                el = page.locator(f'xpath={SEL["input_box"]}')
                el.evaluate(
                    '(node, text) => { node.textContent = text; '
                    'node.dispatchEvent(new Event("input", {bubbles: true})); }',
                    args.prompt,
                )
                page.wait_for_timeout(500)
            except Exception as e:
                fail(f'Step 5 failed: could not type prompt: {e}', failed_step=5)

        # Step 6: Submit
        if start <= 6:
            log('Step 6: Submitting prompt...')
            try:
                page.locator(f'xpath={SEL["send_button"]}').click()
                page.wait_for_timeout(1000)
            except Exception as e:
                fail(f'Step 6 failed: could not submit: {e}', failed_step=6)

        # Step 7: Wait for research plan (confirm button)
        if start <= 7:
            log('Step 7: Waiting for research plan...')
            try:
                deadline = time.time() + 120
                while time.time() < deadline:
                    if page.locator(f'xpath={SEL["confirm_button"]}').count() > 0:
                        break
                    page.wait_for_timeout(2000)
                else:
                    fail('Step 7 failed: research plan did not appear within 120s.', failed_step=7)
            except SystemExit:
                raise
            except Exception as e:
                fail(f'Step 7 failed: error waiting for plan: {e}', failed_step=7)

        # Step 8: Confirm the research plan
        if start <= 8:
            log('Step 8: Confirming research plan...')
            try:
                page.locator(f'xpath={SEL["confirm_button"]}').click()
                page.wait_for_timeout(2000)
            except Exception as e:
                fail(f'Step 8 failed: could not confirm plan: {e}', failed_step=8)

        # Step 9: Wait for research completion
        if start <= 9:
            log(f'Step 9: Waiting for research completion (timeout {args.timeout}s)...')
            try:
                deadline = time.time() + args.timeout
                prev_text_len = 0
                stable_count = 0
                while time.time() < deadline:
                    # Primary signal: sources carousel appears
                    if page.locator(f'xpath={SEL["last_sources"]}').count() > 0:
                        log('Step 9: Sources carousel detected — research complete.')
                        break
                    # Secondary signal: message length stabilized (not growing)
                    # This catches completion even if sources carousel doesn't render.
                    # Require >=5000 chars AND stable for 3 consecutive checks (15s)
                    # to avoid treating mid-stream output as complete.
                    last_msg = page.locator(f'xpath={SEL["last_message"]}')
                    if last_msg.count() > 0:
                        text_len = len(last_msg.first.inner_text() or '')
                        if text_len >= 5000 and text_len == prev_text_len:
                            stable_count += 1
                            if stable_count >= 3:
                                log(f'Step 9: Message stable at {text_len} chars for 15s — research complete.')
                                break
                        else:
                            stable_count = 0
                        prev_text_len = text_len
                    page.wait_for_timeout(5000)
                else:
                    fail(f'Step 9 failed: research did not complete within {args.timeout}s.', failed_step=9)
            except SystemExit:
                raise
            except Exception as e:
                fail(f'Step 9 failed: error waiting for completion: {e}', failed_step=9)

        # Step 10: Extract report and sources
        log('Step 10: Extracting report and sources...')
        try:
            last_msg = page.locator(f'xpath={SEL["last_message"]}').last
            msg_handle = last_msg.element_handle()
            report_md = html_to_markdown(page, msg_handle)

            sources = extract_sources(page)

            report_path = output_dir / 'gemini_deep_research.md'
            sources_path = output_dir / 'gemini_deep_research_sources.json'

            report_path.write_text(report_md, encoding='utf-8')
            sources_path.write_text(
                json.dumps(sources, indent=2, ensure_ascii=False), encoding='utf-8'
            )

            log(f'Report written to {report_path} ({len(report_md)} chars)')
            log(f'Sources written to {sources_path} ({len(sources)} sources)')

            print(json.dumps({
                'success': True,
                'report_path': str(report_path),
                'sources_path': str(sources_path),
                'report_length': len(report_md),
                'source_count': len(sources),
            }, ensure_ascii=False))
        except SystemExit:
            raise
        except Exception as e:
            fail(f'Step 10 failed: could not extract report: {e}', failed_step=10)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    run(args)


if __name__ == '__main__':
    main()
