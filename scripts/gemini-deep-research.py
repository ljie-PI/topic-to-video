#!/usr/bin/env python3
"""通过 Playwright over CDP 自动化 Gemini Deep Research。

向 Google Gemini 的 Deep Research 功能提交一个研究 prompt，并等待完整报告。
浏览器模型：通过 CDP（默认 http://localhost:9222）连到一个 Chrome 进程。若没有可
达的 CDP 响应者，则自动以 --user-data-dir=<profile-dir> 启动系统 Chrome。所需的
profile 与其他工具（harvest-pages 等）共享。退出时 Chrome 保持运行，以便后续调用
能立即重连。复用 CDP 时，被忽略的显式启动参数会在 stderr 以及输出的
chrome.ignored_flags 字段中报告。

自动化始终为自己的工作打开一个全新的标签页，绝不导航用户已打开的标签页。

自检模式（--self-check）不提交任何东西：它只验证 Gemini 已登录、且 Deep Research
入口可达。在开始长时间研究之前使用它。

可恢复性：prompt 提交之后，会话 URL 会立刻写入状态文件（默认
<output-dir>/gemini_deep_research_state.json），并同时嵌入之后任何错误（例如超时）
的失败 JSON（"session_url"）中。要在超时或中断之后从“等待完成”这一步恢复，用保存
下来的 URL 重跑：

  python3 gemini-deep-research.py --output-dir ... --resume \\
    --profile-dir {work_dir}/chrome_profile

用法：
  python3 gemini-deep-research.py \\
    --prompt "关于量子计算的全面综述" \\
    --output-dir ./quantum_computing/ \\
    --profile-dir {work_dir}/chrome_profile

  python3 gemini-deep-research.py --self-check \\
    --profile-dir {work_dir}/chrome_profile

输出约定：
  stdout : 单个 JSON 对象
    success: {"success": true, "report_path": "...", "sources_path": "...",
              "report_length": N, "source_count": N}
    self-check success: {"success": true, "self_check": true}
    error:   {"success": false, "error": "...", "failed_step": N,
              "session_url": "..."}   # session_url 仅在 prompt 提交之后出现
  stderr : 带 `[gemini-deep-research]` 前缀的人类可读进度
  exit   : 0 成功，1 运行时错误，2 参数非法
"""

import argparse
import json
import time
from functools import partial
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
# I/O 辅助函数
# ---------------------------------------------------------------------------

log = cli.make_logger(TOOL_NAME)


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
        cli.fail(TOOL_NAME, f'Could not read resume state file {state_path}: {exc}')
    session_url = state.get('session_url') if isinstance(state, dict) else None
    if not isinstance(session_url, str) or not session_url.strip():
        cli.fail(TOOL_NAME, f'Resume state file {state_path} does not contain session_url')
    args.start_from_step = 9
    args.page_url = session_url


# ---------------------------------------------------------------------------
# HTML 转 Markdown
# ---------------------------------------------------------------------------

def html_to_markdown(page: Any, container_handle: Any) -> str:
    """在浏览器内遍历子树，把该元素的子节点转成 Markdown。"""
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
            // 对 div 等容器递归处理
            let out = '';
            for (const child of el.children) { out += convertNode(child); }
            return out || (inlineText(el) + '\\n\\n');
        }
        // 先找 .markdown 子节点，找不到就用容器自身
        const target = container.querySelector('.markdown') || container;
        let result = '';
        for (const child of target.children) { result += convertNode(child); }
        return result.trim() || target.textContent || '';
    }''', container_handle)
    return md


# ---------------------------------------------------------------------------
# 抽取来源
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
# 主自动化流程
# ---------------------------------------------------------------------------

def run_self_check(args: argparse.Namespace, browser: Any, chrome_metadata: Dict[str, Any]) -> None:
    """只验证登录状态与 Deep Research 入口；不提交任何内容。

    始终在新建的标签页中工作，因此用户已有的标签页绝不会被触碰。failed_step
    取值：2 = 登录，3 = Deep Research 入口。
    """
    if browser.contexts:
        context = browser.contexts[0]
    else:
        context = browser.new_context()
    page = context.new_page()  # 绝不复用已有的标签页
    try:
        log('Self-check: opening Gemini in a new tab...')
        page.goto(GEMINI_URL, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(2000)

        log('Self-check: verifying login state...')
        try:
            page.wait_for_selector(f'xpath={SEL["input_box"]}', timeout=30000)
        except Exception:
            cli.fail(TOOL_NAME, 'Self-check failed: Not logged in to Gemini. Please log in manually first.',
                 failed_step=2)

        log('Self-check: verifying Deep Research entry...')
        try:
            page.locator(f'xpath={SEL["tools_button"]}').click()
            page.wait_for_selector(f'xpath={SEL["deep_research_item"]}', state='visible', timeout=10000)
        except Exception as e:
            cli.fail(TOOL_NAME, f'Self-check failed: Deep Research entry not reachable: {e}', failed_step=3)

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

    # 步骤 1：通过 CDP 连接 Chrome（总是先确保 CDP 就绪）
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
        cli.fail(TOOL_NAME, f'Step 1 failed: could not connect to Chrome: {e}', failed_step=1)

    with chrome_session:
        browser = chrome_session.browser
        chrome_metadata = chrome_session.metadata()
        if args.self_check:
            run_self_check(args, browser, chrome_metadata)
            return

        # prompt 提交后记录会话 URL，这样之后每个失败 JSON 都能带上它用于恢复。
        # 恢复运行（--page-url）会直接以它为种子：步骤 <= 6 都被跳过，因此没有这个
        # 种子的话，第二次超时就会把这个 URL 彻底丢掉。
        session: Dict[str, Any] = {'session_url': args.page_url}
        session_extra = {'session_url': session['session_url']} if session['session_url'] else {}
        session_fail = partial(cli.fail, TOOL_NAME, extra=session_extra)

        # 自动化总是打开一个全新的标签页；绝不导航用户已经打开的标签页。
        if browser.contexts:
            context = browser.contexts[0]
        else:
            context = browser.new_context()
        page = context.new_page()

        # 步骤 2：导航
        if start <= 2:
            nav_url = args.page_url if args.page_url else GEMINI_URL
            log(f'Step 2: Navigating to {nav_url}...')
            try:
                page.goto(nav_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                session_fail(f'Step 2 failed: navigation error: {e}', failed_step=2)
        elif args.page_url:
            log('Step 2: Navigating to provided page URL...')
            try:
                page.goto(args.page_url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
            except Exception as e:
                session_fail(f'Step 2 failed: navigation error: {e}', failed_step=2)

        # 步骤 3：验证登录
        if start <= 3:
            log('Step 3: Verifying Gemini login...')
            try:
                page.wait_for_selector(f'xpath={SEL["input_box"]}', timeout=30000)
            except Exception:
                session_fail('Step 3 failed: Not logged in to Gemini. Please log in manually first.', failed_step=3)

        # 步骤 4：激活 Deep Research 模式
        if start <= 4:
            log('Step 4: Activating Deep Research mode...')
            try:
                page.locator(f'xpath={SEL["tools_button"]}').click()
                page.wait_for_selector(f'xpath={SEL["deep_research_item"]}', state='visible', timeout=10000)
                page.locator(f'xpath={SEL["deep_research_item"]}').first.click()
                page.wait_for_timeout(1500)
            except Exception as e:
                session_fail(f'Step 4 failed: could not activate Deep Research: {e}', failed_step=4)

        # 步骤 5：输入研究 prompt
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
                session_fail(f'Step 5 failed: could not type prompt: {e}', failed_step=5)

        # 步骤 6：提交
        if start <= 6:
            log('Step 6: Submitting prompt...')
            try:
                page.locator(f'xpath={SEL["send_button"]}').click()
                page.wait_for_timeout(1000)
            except Exception as e:
                session_fail(f'Step 6 failed: could not submit: {e}', failed_step=6)

            # 立刻持久化会话 URL：从这里往后，超时或中断都可以用这个 URL 从步骤 9
            # 恢复。
            session['session_url'] = page.url
            if session['session_url']:
                session_extra['session_url'] = session['session_url']
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

        # 步骤 7：等待研究计划（确认按钮）
        if start <= 7:
            log('Step 7: Waiting for research plan...')
            try:
                deadline = time.time() + 120
                while time.time() < deadline:
                    if page.locator(f'xpath={SEL["confirm_button"]}').count() > 0:
                        break
                    page.wait_for_timeout(2000)
                else:
                    session_fail('Step 7 failed: research plan did not appear within 120s.', failed_step=7)
            except SystemExit:
                raise
            except Exception as e:
                session_fail(f'Step 7 failed: error waiting for plan: {e}', failed_step=7)

        # 步骤 8：确认研究计划
        if start <= 8:
            log('Step 8: Confirming research plan...')
            try:
                page.locator(f'xpath={SEL["confirm_button"]}').click()
                page.wait_for_timeout(2000)
            except Exception as e:
                session_fail(f'Step 8 failed: could not confirm plan: {e}', failed_step=8)

        # 步骤 9：等待研究完成
        if start <= 9:
            log(f'Step 9: Waiting for research completion (timeout {args.timeout}s)...')
            try:
                deadline = time.time() + args.timeout
                prev_text_len = 0
                stable_count = 0
                while time.time() < deadline:
                    # 主信号：出现来源 carousel
                    if page.locator(f'xpath={SEL["last_sources"]}').count() > 0:
                        log('Step 9: Sources carousel detected — research complete.')
                        break
                    # 次信号：消息长度稳定（不再增长）
                    # 即使来源 carousel 没有渲染出来，这也能捕获完成状态。
                    # 要求 >=5000 字符且连续 3 次检查（15s）保持稳定，
                    # 以免把流式输出的中途当成已完成。
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
                    session_fail(f'Step 9 failed: research did not complete within {args.timeout}s.', failed_step=9)
            except SystemExit:
                raise
            except Exception as e:
                session_fail(f'Step 9 failed: error waiting for completion: {e}', failed_step=9)

        # 步骤 10：抽取报告与来源
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
            session_fail(f'Step 10 failed: could not extract report: {e}', failed_step=10)


# ---------------------------------------------------------------------------
# 入口点
# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    apply_resume_state(args)
    run(args)


if __name__ == '__main__':
    raise SystemExit(cli.run(main, TOOL_NAME))
