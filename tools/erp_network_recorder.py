from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
import argparse
import json
import os
import re
import sys
import time
import traceback

from playwright.sync_api import sync_playwright


DEFAULT_START_URL = "http://58.72.235.17:8100/"
DEFAULT_OUTPUT_DIR = Path("output") / "playwright"
MAX_BODY_CHARS = 20000
SENSITIVE_RE = re.compile(
    r"(password|passwd|pwd|pass|token|secret|cookie|authorization|requestverification|csrf|"
    r"lvalue|ldata|convalue|devvalue|loginiv|loginkey|verification)",
    re.I,
)
TEXT_CT_RE = re.compile(r"(json|text|xml|html|javascript|x-www-form-urlencoded)", re.I)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def mask_obj(value):
    if isinstance(value, dict):
        return {
            key: ("<MASKED>" if SENSITIVE_RE.search(str(key)) else mask_obj(child))
            for key, child in value.items()
        }
    if isinstance(value, list):
        return [mask_obj(child) for child in value]
    return value


def mask_url(url: str) -> str:
    parsed = urlsplit(url)
    if not parsed.query:
        return url
    query = []
    for key, value in parse_qsl(parsed.query, keep_blank_values=True):
        query.append((key, "<MASKED>" if SENSITIVE_RE.search(key) else value))
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(query), parsed.fragment))


def mask_text(text: str | None) -> str | None:
    if text is None:
        return None
    if not isinstance(text, str):
        text = str(text)

    try:
        parsed = json.loads(text)
        return json.dumps(mask_obj(parsed), ensure_ascii=False)[:MAX_BODY_CHARS]
    except Exception:
        pass

    patterns = [
        (
            r"(?i)((?:password|passwd|pwd|pass|token|secret|cookie|authorization|"
            r"requestverification|csrf|lvalue|ldata|convalue|devvalue|loginiv|loginkey|"
            r"__RequestVerificationToken)=)([^&\s]+)",
            r"\1<MASKED>",
        ),
        (
            r"(?i)((?:password|passwd|pwd|pass|token|secret|cookie|authorization|"
            r"requestverification|csrf|lvalue|ldata|convalue|devvalue|loginiv|loginkey)"
            r"\s*[:=]\s*['\"])([^'\"]*)(['\"])",
            r"\1<MASKED>\3",
        ),
        (
            r"(?is)(<input\b(?=[^>]*\bname=['\"][^'\"]*(?:token|verification|password|"
            r"lvalue|ldata|convalue|devvalue|loginiv|loginkey)[^'\"]*['\"])[^>]*\bvalue=['\"])([^'\"]*)(['\"])",
            r"\1<MASKED>\3",
        ),
    ]
    masked = text
    for pattern, replacement in patterns:
        masked = re.sub(pattern, replacement, masked)
    return masked[:MAX_BODY_CHARS]


def mask_headers(headers: dict[str, str]) -> dict[str, str]:
    return {
        key: ("<MASKED>" if SENSITIVE_RE.search(key) else value)
        for key, value in headers.items()
    }


def selector_hints(payload: dict) -> list[str]:
    hints = []
    if payload.get("id"):
        hints.append("#" + payload["id"])
    if payload.get("name"):
        hints.append(f'[name="{payload["name"]}"]')
    if payload.get("dataTestid"):
        hints.append(f'[data-testid="{payload["dataTestid"]}"]')
    if payload.get("text"):
        hints.append(f'text="{payload["text"][:60]}"')
    return hints


def build_paths(output_dir: Path, log: Path | None, profile: Path | None) -> tuple[Path, Path]:
    run_id = stamp()
    output_dir.mkdir(parents=True, exist_ok=True)
    return (
        log or output_dir / f"network-record-{run_id}.jsonl",
        profile or output_dir / f"profile-{run_id}",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Open a headed Playwright browser and record ERP UI actions plus Network request/response logs."
    )
    parser.add_argument("--url", default=DEFAULT_START_URL, help=f"start URL, default: {DEFAULT_START_URL}")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--log", type=Path, help="JSONL log path")
    parser.add_argument("--profile", type=Path, help="persistent Chromium profile path")
    parser.add_argument("--max-body-chars", type=int, default=MAX_BODY_CHARS)
    parser.add_argument("--include-document-body", action="store_true", help="also store document HTML bodies")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    global MAX_BODY_CHARS
    MAX_BODY_CHARS = args.max_body_chars

    log_path, profile_path = build_paths(args.output_dir, args.log, args.profile)
    profile_path.mkdir(parents=True, exist_ok=True)

    with log_path.open("a", encoding="utf-8", buffering=1) as log_file:

        def write(event: dict) -> None:
            event.setdefault("ts", now_iso())
            log_file.write(json.dumps(event, ensure_ascii=False) + "\n")
            log_file.flush()

        with sync_playwright() as p:
            context = p.chromium.launch_persistent_context(
                str(profile_path),
                headless=False,
                viewport={"width": 1440, "height": 900},
                args=["--window-size=1440,900"],
            )

            def on_action(source, payload):
                try:
                    payload = dict(payload)
                    payload["selectorHints"] = selector_hints(payload)
                    page = source.get("page")
                    write({"kind": "ui_action", "pageUrl": page.url if page else None, "payload": payload})
                except Exception:
                    write({"kind": "recorder_error", "where": "on_action", "error": traceback.format_exc()})

            context.expose_binding("pwNetworkRecorderAction", on_action)
            context.add_init_script(
                r"""
(() => {
  const installBadge = () => {
    if (document.getElementById('__pw_rec_badge')) return;
    const badge = document.createElement('div');
    badge.id = '__pw_rec_badge';
    badge.textContent = 'REC Playwright Network';
    badge.style.cssText = 'position:fixed;right:10px;top:10px;z-index:2147483647;background:#b91c1c;color:white;font:12px Arial,sans-serif;padding:4px 8px;border-radius:4px;pointer-events:none;box-shadow:0 1px 4px rgba(0,0,0,.25)';
    document.documentElement.appendChild(badge);
  };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', installBadge);
  else installBadge();

  const textOf = el => (el.innerText || el.value || el.getAttribute('aria-label') || el.title || '').trim().slice(0, 120);
  const payloadOf = (kind, el) => ({
    event: kind,
    tag: el && el.tagName ? el.tagName.toLowerCase() : null,
    text: el ? textOf(el) : '',
    id: el ? (el.id || null) : null,
    name: el ? el.getAttribute('name') : null,
    type: el ? el.getAttribute('type') : null,
    className: el ? String(el.className || '').slice(0, 160) : null,
    dataTestid: el ? el.getAttribute('data-testid') : null
  });

  document.addEventListener('click', e => {
    const el = e.target && e.target.closest
      ? e.target.closest('button,input,a,select,textarea,[role="button"],td,th,li,div,span')
      : e.target;
    if (window.pwNetworkRecorderAction) window.pwNetworkRecorderAction(payloadOf('click', el)).catch(() => {});
  }, true);

  document.addEventListener('change', e => {
    const payload = payloadOf('change', e.target);
    payload.valueRecorded = false;
    if (window.pwNetworkRecorderAction) window.pwNetworkRecorderAction(payload).catch(() => {});
  }, true);
})();
"""
            )

            def on_request(req) -> None:
                if req.resource_type not in ("xhr", "fetch", "document"):
                    return
                write(
                    {
                        "kind": "request",
                        "method": req.method,
                        "url": mask_url(req.url),
                        "resourceType": req.resource_type,
                        "headers": mask_headers(req.headers),
                        "postData": mask_text(req.post_data),
                    }
                )

            def on_response(res) -> None:
                req = res.request
                if req.resource_type not in ("xhr", "fetch", "document"):
                    return
                content_type = res.headers.get("content-type", "")
                event = {
                    "kind": "response",
                    "status": res.status,
                    "url": mask_url(res.url),
                    "resourceType": req.resource_type,
                    "contentType": content_type,
                    "headers": mask_headers(res.headers),
                }
                should_store_body = req.resource_type in ("xhr", "fetch") or args.include_document_body
                if should_store_body and TEXT_CT_RE.search(content_type):
                    try:
                        event["body"] = mask_text(res.text())
                    except Exception as exc:
                        event["bodyError"] = str(exc)
                else:
                    event["bodyOmitted"] = "document body omitted" if req.resource_type == "document" else "non-text content-type"
                write(event)

            context.on("request", on_request)
            context.on("response", on_response)
            context.on("page", lambda page: write({"kind": "page_opened", "url": mask_url(page.url)}))

            page = context.pages[0] if context.pages else context.new_page()
            write(
                {
                    "kind": "recorder_started",
                    "startUrl": args.url,
                    "logPath": str(log_path),
                    "profilePath": str(profile_path),
                    "pid": os.getpid(),
                }
            )
            page.goto(args.url, wait_until="domcontentloaded", timeout=30000)
            print("PLAYWRIGHT_RECORDING_OPEN", flush=True)
            print(f"PID={os.getpid()}", flush=True)
            print(f"LOG={log_path}", flush=True)
            print(f"PROFILE={profile_path}", flush=True)

            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                write({"kind": "recorder_stopped"})
            finally:
                context.close()

    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        raise
