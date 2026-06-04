---
name: erp-network-recorder
description: Open a headed Playwright recording browser for ERP/RPA training sites and capture UI actions plus Network request/response logs. Use when the user asks to run Playwright in recording mode, capture DevTools Network automatically, identify which ERP button/menu creates which WebApi request, or analyze a recorded ERP automation flow in this project.
---

# ERP Network Recorder

Use this project-local skill to launch a visible Playwright browser that the user can operate manually while Codex records UI actions and Network traffic to JSONL.

## Quick Start

Run the project bundled script from the repository root:

```powershell
python .codex\skills\erp-network-recorder\scripts\erp_network_recorder.py --url "http://58.72.235.17:8100/"
```

The same implementation is also available as:

```powershell
python tools\erp_network_recorder.py --url "http://58.72.235.17:8100/"
```

Tell the user to operate only the browser window with the red `REC Playwright Network` badge. Do not ask the user to open DevTools; DevTools can trigger `Paused in debugger` and is unnecessary because the script records Network events directly.

## What Gets Recorded

- UI click/change events with best-effort selector hints
- XHR/fetch/document request method, URL, headers, and POST body
- XHR/fetch response status, headers, and text/JSON body
- Document response metadata, with document body omitted by default
- A persistent Playwright profile path for that run

Sensitive keys in URLs, headers, JSON, forms, and HTML-style values are masked where possible. Still treat logs as local-sensitive artifacts and do not paste full logs into chat unless the user explicitly asks and sensitive values are reviewed.

## Analysis Workflow

After the user completes a flow:

1. Find the latest `network-record-*.jsonl` under `output/playwright/`.
2. Summarize `ui_action`, `request`, and `response` events in timestamp order.
3. Group nearby UI actions and WebApi requests into likely operations.
4. Report clicked menu/button text, selector hints, request method/URL, POST payload shape, response status, and which request is likely the target 조회/search API.

Use concise PowerShell inspection when possible:

```powershell
$path = Get-ChildItem output\playwright -Filter 'network-record-*.jsonl' |
  Sort-Object LastWriteTime -Descending |
  Select-Object -First 1 -ExpandProperty FullName
Get-Content $path | ForEach-Object {
  $e = $_ | ConvertFrom-Json
  [pscustomobject]@{
    ts = $e.ts
    kind = $e.kind
    method = $e.method
    status = $e.status
    url = ($e.url -replace '\?.*$', '')
    ui = $e.payload.event
    text = $e.payload.text
    id = $e.payload.id
    type = $e.resourceType
  }
} | Format-Table -AutoSize
```

## Safety

- Prefer read/query flows. Do not click real save/submit/update buttons unless the user explicitly confirms.
- Keep `output/playwright/` out of git. It can contain cookies, profiles, and business data even with masking.
- If a recording process dies or stops appending events, restart a fresh recording window. Multiple Chrome windows are easy to confuse; use the red `REC Playwright Network` badge as the source of truth.
