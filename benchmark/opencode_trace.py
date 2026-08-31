#!/usr/bin/env python3
"""Utilities for preserving and summarizing OpenCode CLI trajectories.

The benchmark archives both the raw ``opencode run --format json`` event stream
and, when a session id can be recovered, ``opencode export`` output.  Export is
used as the authoritative fallback because some OpenCode versions have had
stdout event-drain races in non-interactive mode.
"""
from __future__ import annotations

import argparse
import base64
import json
import re
from pathlib import Path
from typing import Any


VERDICTS = {"PASS", "FAIL", "ABSTAIN"}

# Prefer an explicit machine-readable marker, but tolerate common Markdown
# formatting because model outputs are not guaranteed to obey formatting
# instructions exactly. Conflicting explicit verdicts intentionally fail
# closed instead of guessing.
VERDICT_MARKER_RE = re.compile(
    r"(?im)^\s*(?:[#>*+\-]\s*)*"
    r"(?:[*_`~]{0,3})"
    r"(?:DRIFTGUARD[_ \-]?VERDICT|FINAL\s+VERDICT|VERDICT)"
    r"(?:[*_`~]{0,3})\s*[:=\-]\s*"
    r"(?:[*_`~]{0,3})(PASS|FAIL|ABSTAIN)\b",
    re.IGNORECASE,
)
JSON_VERDICT_RE = re.compile(
    r'[\"\']verdict[\"\']\s*:\s*[\"\'](PASS|FAIL|ABSTAIN)[\"\']',
    re.IGNORECASE,
)


def read_events(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    if not path.exists():
        return events
    for raw in path.read_text(errors="replace").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        try:
            obj = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict):
            events.append(obj)
    return events


def load_export(path: Path | None) -> dict[str, Any] | None:
    if path is None or not path.exists():
        return None
    raw = path.read_text(errors="replace").strip()
    if not raw:
        return None
    # Older OpenCode versions sometimes prefixed a status line before JSON.
    starts = [i for i in (raw.find("{"), raw.find("[")) if i >= 0]
    if starts:
        raw = raw[min(starts) :]
    try:
        obj = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return obj if isinstance(obj, dict) else {"data": obj}


def event_session_id(events: list[dict[str, Any]]) -> str | None:
    for event in events:
        sid = event.get("sessionID") or event.get("sessionId")
        if isinstance(sid, str) and sid:
            return sid
        part = event.get("part")
        if isinstance(part, dict):
            sid = part.get("sessionID") or part.get("sessionId")
            if isinstance(sid, str) and sid:
                return sid
    return None


def text_from_events(events: list[dict[str, Any]]) -> list[str]:
    texts: list[str] = []
    for event in events:
        if event.get("type") != "text":
            continue
        part = event.get("part")
        if isinstance(part, dict):
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return texts


def export_messages(export: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not export:
        return []
    messages = export.get("messages")
    if not isinstance(messages, list):
        return []
    out = [m for m in messages if isinstance(m, dict)]

    def created(m: dict[str, Any]) -> int:
        info = m.get("info")
        if not isinstance(info, dict):
            return 0
        time = info.get("time")
        if not isinstance(time, dict):
            return 0
        value = time.get("created")
        return int(value) if isinstance(value, (int, float)) else 0

    # Current exports are normally chronological, but sorting by explicit time
    # protects us from historical export-order bugs.
    return sorted(out, key=created)


def final_text_from_export(export: dict[str, Any] | None) -> str | None:
    candidates: list[tuple[int, str]] = []
    for idx, msg in enumerate(export_messages(export)):
        info = msg.get("info")
        if not isinstance(info, dict) or info.get("role") != "assistant":
            continue
        parts = msg.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            text = part.get("text")
            if isinstance(text, str) and text.strip():
                candidates.append((idx, text.strip()))
    return candidates[-1][1] if candidates else None


def usage_from_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    total = {"input": 0, "output": 0, "reasoning": 0, "cache_read": 0, "cache_write": 0}
    cost = 0.0
    finishes = 0
    for event in events:
        if event.get("type") != "step_finish":
            continue
        part = event.get("part")
        if not isinstance(part, dict):
            continue
        finishes += 1
        if isinstance(part.get("cost"), (int, float)):
            cost += float(part["cost"])
        tokens = part.get("tokens")
        if not isinstance(tokens, dict):
            continue
        for key in ("input", "output", "reasoning"):
            if isinstance(tokens.get(key), (int, float)):
                total[key] += int(tokens[key])
        cache = tokens.get("cache")
        if isinstance(cache, dict):
            if isinstance(cache.get("read"), (int, float)):
                total["cache_read"] += int(cache["read"])
            if isinstance(cache.get("write"), (int, float)):
                total["cache_write"] += int(cache["write"])
    return {"step_finishes_seen": finishes, "cost": round(cost, 8), "tokens": total}


def tools_from_events(events: list[dict[str, Any]]) -> list[str]:
    tools: list[str] = []
    for event in events:
        if event.get("type") != "tool_use":
            continue
        part = event.get("part")
        if isinstance(part, dict) and isinstance(part.get("tool"), str):
            tools.append(part["tool"])
    return tools


def model_from_export(export: dict[str, Any] | None) -> dict[str, Any]:
    for msg in reversed(export_messages(export)):
        info = msg.get("info")
        if not isinstance(info, dict) or info.get("role") != "assistant":
            continue
        model = info.get("model")
        result: dict[str, Any] = {}
        if isinstance(model, dict):
            result.update({k: v for k, v in model.items() if k in {"providerID", "modelID", "variant"}})
        elif isinstance(info.get("modelID"), str):
            result["modelID"] = info.get("modelID")
        if isinstance(info.get("variant"), str):
            result.setdefault("variant", info.get("variant"))
        if isinstance(info.get("agent"), str):
            result["agent"] = info.get("agent")
        if result:
            return result
    return {}


def _unique_verdict(values: list[str]) -> str | None:
    normalized = {value.upper() for value in values if value.upper() in VERDICTS}
    if len(normalized) == 1:
        return next(iter(normalized))
    return None


def _strip_markdown_prefix(line: str) -> str:
    value = line.strip()
    # Repeatedly remove ordinary Markdown structural prefixes. This accepts
    # outputs such as "# Fail", "> **PASS**", and "- `ABSTAIN`" while not
    # searching arbitrary prose for verdict words.
    prefix = re.compile(r"^(?:#{1,6}\s+|>\s*|[-+*]\s+|\d+[.)]\s+)")
    while True:
        updated = prefix.sub("", value, count=1).strip()
        if updated == value:
            break
        value = updated
    return value


def _standalone_verdict(line: str) -> str | None:
    value = _strip_markdown_prefix(line)
    # Strip balanced-ish inline Markdown decorations around the verdict.
    value = re.sub(r"^[*_`~]+", "", value)
    value = re.sub(r"[*_`~]+$", "", value).strip()
    match = re.match(
        r"^(PASS|FAIL|ABSTAIN)\b(?:\s*(?::|[-–—])\s*.*)?$",
        value,
        re.IGNORECASE,
    )
    return match.group(1).upper() if match else None


def extract_verdict(text: str | None) -> str | None:
    if not text:
        return None

    # 1) Strongest signal: explicit verdict marker anywhere in the response.
    explicit = [m.group(1) for m in VERDICT_MARKER_RE.finditer(text)]
    if explicit:
        return _unique_verdict(explicit)

    # 2) Structured JSON-like output. Code fences are fine because this regex
    # only recognizes an explicit `verdict` key.
    structured = [m.group(1) for m in JSON_VERDICT_RE.finditer(text)]
    if structured:
        return _unique_verdict(structured)

    # 3) Backward-compatible human formatting. Inspect only the opening and
    # closing significant lines so words inside explanatory prose cannot
    # accidentally become control flow.
    lines = [line for line in text.splitlines() if line.strip()]
    candidates: list[str] = []
    for line in lines[:8] + (lines[-8:] if len(lines) > 8 else []):
        verdict = _standalone_verdict(line)
        if verdict:
            candidates.append(verdict)
    return _unique_verdict(candidates) if candidates else None


def build_web_url(base_url: str, directory: str, session_id: str | None = None) -> str:
    slug = base64.urlsafe_b64encode(directory.encode("utf-8")).decode("ascii").rstrip("=")
    url = f"{base_url.rstrip('/')}/{slug}/session"
    if session_id:
        url += f"/{session_id}"
    return url


def summarize(events_path: Path, export_path: Path | None) -> dict[str, Any]:
    events = read_events(events_path)
    exported = load_export(export_path)
    final_text = final_text_from_export(exported)
    source = "export"
    if not final_text:
        texts = text_from_events(events)
        final_text = texts[-1] if texts else ""
        source = "events"
    event_types: dict[str, int] = {}
    for event in events:
        t = str(event.get("type", "unknown"))
        event_types[t] = event_types.get(t, 0) + 1
    return {
        "session_id": event_session_id(events) or (exported or {}).get("info", {}).get("id"),
        "final_text_source": source,
        "final_text": final_text,
        "verdict": extract_verdict(final_text),
        "event_counts": event_types,
        "tools": tools_from_events(events),
        "usage_from_stream": usage_from_events(events),
        "model": model_from_export(exported),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)

    sid = sub.add_parser("session-id")
    sid.add_argument("events", type=Path)

    summ = sub.add_parser("summarize")
    summ.add_argument("events", type=Path)
    summ.add_argument("--export", type=Path)
    summ.add_argument("--output", type=Path, required=True)
    summ.add_argument("--text-output", type=Path)

    web = sub.add_parser("web-url")
    web.add_argument("base_url")
    web.add_argument("directory")
    web.add_argument("--session-id")

    verdict = sub.add_parser("verdict")
    verdict.add_argument("text_file", type=Path)

    args = p.parse_args()
    if args.cmd == "session-id":
        value = event_session_id(read_events(args.events))
        if value:
            print(value)
            raise SystemExit(0)
        raise SystemExit(1)

    if args.cmd == "web-url":
        print(build_web_url(args.base_url, args.directory, args.session_id))
        raise SystemExit(0)

    if args.cmd == "verdict":
        value = extract_verdict(args.text_file.read_text(errors="replace"))
        if value:
            print(value)
            raise SystemExit(0)
        raise SystemExit(1)

    payload = summarize(args.events, args.export)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
    if args.text_output:
        args.text_output.write_text(str(payload.get("final_text") or "") + "\n")
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
