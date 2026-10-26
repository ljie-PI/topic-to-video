#!/usr/bin/env python3
"""Gemini Deep Research automation via Playwright over CDP.

Submits a research prompt to Google Gemini's Deep Research feature and waits
for the full report.  Browser model: attaches over CDP (default
http://localhost:9222) to a Chrome process.  If no CDP responder is reachable,
auto-launches system Chrome with --user-data-dir=<profile-dir>. The required
profile is SHARED with other tools (harvest-pages, etc.). Chrome is left running
on exit so subsequent invocations reconnect instantly. When reusing CDP, explicit
launch flags are reported in stderr and the output's chrome.ignored_flags field.

The automation ALWAYS opens a brand-new browser tab for its work and never
navigates any tab the user already had open.

Self-check mode (--self-check) submits nothing: it only verifies that Gemini
is logged in and that the Deep Research entry is reachable.  Use it before
starting a long research run.

Resumability: immediately after the prompt is submitted, the session URL is
written to a state file (default <output-dir>/gemini_deep_research_state.json)
and is also embedded in the failure JSON ("session_url") of any later error
(e.g. timeout).  To resume from the wait-for-completion step after a timeout
or interruption, re-run with the saved URL:

  python3 gemini-deep-research.py --output-dir ... --resume \\
    --profile-dir {work_dir}/chrome_profile

Usage:
  python3 gemini-deep-research.py \\
    --prompt "关于量子计算的全面综述" \\
    --output-dir ./quantum_computing/ \\
    --profile-dir {work_dir}/chrome_profile

  python3 gemini-deep-research.py --self-check \\
    --profile-dir {work_dir}/chrome_profile

Output convention:
  stdout : single JSON object
    success: {"success": true, "report_path": "...", "sources_path": "...",
              "report_length": N, "source_count": N}
    self-check success: {"success": true, "self_check": true}
    error:   {"success": false, "error": "...", "failed_step": N,
              "session_url": "..."}   # session_url only once the prompt
                                      # has been submitted
  stderr : human-readable progress prefixed with `[gemini-deep-research]`
  exit   : 0 success, 1 runtime error, 2 invalid arguments
"""

import argparse
import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import chrome_cdp
import cli

TOOL_NAME = 'gemini-deep-research'
DEFAULT_CDP_URL = 'http://localhost:9222'
CHROME_WINDOW_SIZE = '1680,1680'

GEMINI_URL = 'https://gemini.google.com/app'

SEL = {
    'input_box': "//div[contains(@class,'ql-editor') and @role='textbox']",
    'send_button': "//button[@aria-label='发送' or @aria-label='Send message' or @aria-label='Send' or contains(@class,'send-button')]",
    'tools_button': "//button[contains(@class,'toolbox-drawer-button') or @aria-label='上传和工具' or @aria-label='Upload and tools' or contains(@aria-label,'Tools')]",
    'tool_menu': "//toolbox-drawer | //mat-action-list[@id='toolbox-drawer-menu'] | //mat-action-list[contains(@class,'menu-list-container')]",
    'deep_research_item': (
        "//toolbox-drawer-item[.//*[contains(normalize-space(text()),'Deep Research')"
        " or contains(normalize-space(text()),'深度研究')]]"
        " | //mat-action-list//button[.//*[contains(normalize-space(text()),'Deep Research')"
        " or contains(normalize-space(text()),'深度研究')]]"
        " | //mat-action-list//button[contains(normalize-space(.),'Deep Research')]"
    ),
    'confirm_button': "//button[@aria-label='Start research' or @data-test-id='confirm-button' or contains(normalize-space(.),'Start research') or contains(normalize-space(.),'开始研究')]",
    'last_message': "(//message-content)[last()]",
    'last_sources': "(//message-content)[last()]//sources-carousel-inline",
}


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

log = cli.make_logger(TOOL_NAME)


def fail(message: str, exit_code: int = 1, failed_step: Optional[int] = None,
         extra: Optional[Dict[str, Any]] = None) -> None:
    log(message)
    obj: Dict[str, Any] = {'success': False, 'error': message}
    if failed_step is not None:
        obj['failed_step'] = failed_step
    if extra:
        obj.update(extra)
    cli.print_json(obj)
    raise SystemExit(exit_code)


def parse_args() -> argparse.Namespace:
    p = cli.JsonArgumentParser(TOOL_NAME, description='Gemini Deep Research automation (Playwright over CDP).')
    p.add_argument('--prompt', default=None, help='Research prompt to submit to Gemini Deep Research.')
    p.add_argument('--output-dir', default=None, help='Directory for report and sources output files.')
    p.add_argument('--self-check', action='store_true',
                   help='Only verify login state and Deep Research entry; submit no prompt.')
    p.add_argument('--state-file', default=None,
                   help='State file for the session URL (default <output-dir>/gemini_deep_research_state.json).')
    p.add_argument('--resume', action='store_true',
                   help='Resume step 9 using session_url from the state file; --prompt is optional.')
    p.add_argument('--cdp-url', default=DEFAULT_CDP_URL,
                   help=f'CDP endpoint (default {DEFAULT_CDP_URL}).')
    p.add_argument('--profile-dir', required=True,
                   help='Chrome profile dir (required; use the shared work_dir profile).')
    p.add_argument('--chrome-path', default=None,
                   help='Path to Chrome executable. Auto-detected if unset.')
    p.add_argument('--headless', default=None, choices=('auto', 'on', 'off'),
                   help="Chrome headless mode. Default 'off' — this script needs a real logged-in Chrome session.")
    p.add_argument('--no-sandbox', action='store_true', default=None,
                   help='Pass --no-sandbox to Chrome (auto-enabled when running as root or inside a container).')
    p.add_argument('--timeout', type=int, default=1800,
                   help='Timeout in seconds for deep research completion (default 1800).')
    p.add_argument('--start-from-step', type=int, default=1, choices=range(1, 11),
                   metavar='[1-10]',
                   help='Resume from a specific step (1-10, default 1). Step 9 = wait for completion.')
    p.add_argument('--page-url', default=None,
                   help='Existing Gemini conversation URL to resume from.')
    args = p.parse_args()
    args.explicit_headless = args.headless
    args.headless = args.headless or 'off'
    if not args.self_check:
        required = [('--output-dir', args.output_dir)]
        if not args.resume:
            required.append(('--prompt', args.prompt))
        missing = [name for name, value in required if not value]
        if missing:
            p.error(f'the following arguments are required (unless --self-check): {", ".join(missing)}')
    return args


def apply_resume_state(args: argparse.Namespace) -> None:
    if not args.resume:
        return
    state_path = Path(args.state_file).expanduser() if args.state_file else (
        Path(args.output_dir).expanduser() / 'gemini_deep_research_state.json'
    )
    try:
        state = json.loads(state_path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        fail(f'Could not read resume state file {state_path}: {exc}')
    session_url = state.get('session_url') if isinstance(state, dict) else None
    if not isinstance(session_url, str) or not session_url.strip():
        fail(f'Resume state file {state_path} does not contain session_url')
    args.start_from_step = 9
    args.page_url = session_url


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

def run_self_check(args: argparse.Namespace, browser: Any, chrome_metadata: Dict[str, Any]) -> None:
    """Verify login state + Deep Research entry only; submit nothing.

    Always works in a freshly opened tab so the user's existing tabs are
    never touched. failed_step values: 2 = login, 3 = deep research entry.
    """
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context()
    page = context.new_page()  # NEVER reuse an existing tab
    try:
        log('Self-check: opening Gemini in a new tab...')
        page.goto(GEMINI_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(2000)

        log('Self-check: verifying login state...')
        try:
            page.wait_for_selector(f'xpath={SEL["input_box"]}', timeout=30000)
        except Exception:
            fail('Self-check failed: Not logged in to Gemini. Please log in manually first.',
                 failed_step=2)

        log('Self-check: verifying Deep Research entry...')
        try:
            page.locator(f'xpath={SEL["tools_button"]}').click()
            page.wait_for_selector(f'xpath={SEL["deep_research_item"]}', state='visible', timeout=10000)
        except Exception as e:
            fail(f'Self-check failed: Deep Research entry not reachable: {e}', failed_step=3)

        cli.print_json({'success': True, 'self_check': True, 'chrome': chrome_metadata})
    finally:
        try:
            page.close()
        except Exception:
            pass


def run(args: argparse.Namespace) -> None:
    output_dir = Path(args.output_dir).expanduser() if args.output_dir else None
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
    start = args.start_from_step

    # Step 1: Connect to Chrome via CDP (always ensure CDP is ready)
    log('Step 1: Connecting to Chrome via CDP...')
    try:
        chrome_session = chrome_cdp.attach_or_launch(
            args.cdp_url,
            args.profile_dir,
            headless=args.explicit_headless,
            window_size=CHROME_WINDOW_SIZE,
            no_sandbox=args.no_sandbox,
            chrome_path=args.chrome_path,
        )
    except Exception as e:
        fail(f'Step 1 failed: could not connect to Chrome: {e}', failed_step=1)

    with chrome_session:
        browser = chrome_session.browser
        chrome_metadata = chrome_session.metadata()
        if args.self_check:
            run_self_check(args, browser, chrome_metadata)
            return

        # Track the session URL once the prompt has been submitted, so every
        # subsequent failure JSON can carry it for resuming.  A resumed run
        # (--page-url) seeds it directly: steps <= 6 are skipped, so without
        # the seed a second timeout would lose the URL entirely.
        session: Dict[str, Any] = {'session_url': args.page_url}

        def fail_with_session(message: str, exit_code: int = 1,
                              failed_step: Optional[int] = None) -> None:
            extra = {'session_url': session['session_url']} if session['session_url'] else None
            fail(message, exit_code, failed_step, extra=extra)

        # ALWAYS open a brand-new tab for the automation; never navigate a tab
        # the user already had open.
        if browser.contexts:
            context = browser.contexts[0]
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
                fail_with_session(f'Step 2 failed: navigation error: {e}', failed_step=2)
        elif args.page_url:
            log('Step 2: Navigating to provided page URL...')
            try:
                page.goto(args.page_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                fail_with_session(f'Step 2 failed: navigation error: {e}', failed_step=2)

        # Step 3: Verify login
        if start <= 3:
            log('Step 3: Verifying Gemini login...')
            try:
                page.wait_for_selector(f'xpath={SEL["input_box"]}', timeout=30000)
            except Exception:
                fail_with_session('Step 3 failed: Not logged in to Gemini. Please log in manually first.', failed_step=3)

        # Step 4: Activate Deep Research mode
        if start <= 4:
            log('Step 4: Activating Deep Research mode...')
            try:
                page.locator(f'xpath={SEL["tools_button"]}').click()
                page.wait_for_selector(f'xpath={SEL["deep_research_item"]}', state='visible', timeout=10000)
                page.locator(f'xpath={SEL["deep_research_item"]}').first.click()
                page.wait_for_timeout(1500)
            except Exception as e:
                fail_with_session(f'Step 4 failed: could not activate Deep Research: {e}', failed_step=4)

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
                fail_with_session(f'Step 5 failed: could not type prompt: {e}', failed_step=5)

        # Step 6: Submit
        if start <= 6:
            log('Step 6: Submitting prompt...')
            try:
                page.locator(f'xpath={SEL["send_button"]}').click()
                page.wait_for_timeout(1000)
            except Exception as e:
                fail_with_session(f'Step 6 failed: could not submit: {e}', failed_step=6)

            # IMMEDIATELY persist the session URL: from here on, a timeout or
            # interruption can be resumed from step 9 with this URL.
            session['session_url'] = page.url
            state_path = Path(args.state_file).expanduser() if args.state_file \
                else output_dir / 'gemini_deep_research_state.json'
            state_path.parent.mkdir(parents=True, exist_ok=True)
            state_payload = {
                'session_url': session['session_url'],
                'state_file_version': 1,
            }
            state_path.write_text(
                json.dumps(state_payload, indent=2, ensure_ascii=False), encoding='utf-8'
            )
            log(f'Session URL saved to {state_path}')

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
                    fail_with_session('Step 7 failed: research plan did not appear within 120s.', failed_step=7)
            except SystemExit:
                raise
            except Exception as e:
                fail_with_session(f'Step 7 failed: error waiting for plan: {e}', failed_step=7)

        # Step 8: Confirm the research plan
        if start <= 8:
            log('Step 8: Confirming research plan...')
            try:
                page.locator(f'xpath={SEL["confirm_button"]}').click()
                page.wait_for_timeout(2000)
            except Exception as e:
                fail_with_session(f'Step 8 failed: could not confirm plan: {e}', failed_step=8)

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
                    fail_with_session(f'Step 9 failed: research did not complete within {args.timeout}s.', failed_step=9)
            except SystemExit:
                raise
            except Exception as e:
                fail_with_session(f'Step 9 failed: error waiting for completion: {e}', failed_step=9)

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

            cli.print_json({
                'success': True,
                'report_path': str(report_path),
                'sources_path': str(sources_path),
                'report_length': len(report_md),
                'source_count': len(sources),
                'session_url': session['session_url'],
                'chrome': chrome_metadata,
            })
        except SystemExit:
            raise
        except Exception as e:
            fail_with_session(f'Step 10 failed: could not extract report: {e}', failed_step=10)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    apply_resume_state(args)
    run(args)


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
