#!/usr/bin/env python3
import argparse
import os
import re
import sys
from pathlib import Path

WRANGLER_PATH = Path("wrangler.toml")
WORKER_NAME_PLACEHOLDER = "__CF_WORKER_NAME__"
KV_NAMESPACE_ID_PLACEHOLDER = "__CF_KV_NAMESPACE_ID__"


def require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"missing required secret: {name}", file=sys.stderr)
        raise SystemExit(1)
    return value


def replace_name(text: str, worker_name: str) -> str:
    if not re.search(r"^name\s*=", text, flags=re.M):
        raise SystemExit("wrangler.toml is missing the name field")
    return re.sub(r'^name\s*=.*$', f'name = "{worker_name}"', text, count=1, flags=re.M)


def replace_kv_binding(text: str, kv_namespace_id: str) -> str:
    desired = (
        '[[kv_namespaces]]\n'
        'binding = "KV"\t\t\t#KV绑定名默认不可修改\n'
        f'id = "{kv_namespace_id}"\t\t\t\t#KV数据库id'
    )
    commented_block = re.compile(
        r'^#\[\[kv_namespaces\]\]\s*\n'
        r'^#binding = "KV"\s*#KV绑定名默认不可修改\s*\n'
        r'^#id = ""\s*#KV数据库id\s*$',
        flags=re.M,
    )
    active_block = re.compile(
        r'^\[\[kv_namespaces\]\]\s*\n'
        r'^binding = "KV"\s*#KV绑定名默认不可修改\s*\n'
        r'^id = ".*"\s*#KV数据库id\s*$',
        flags=re.M,
    )
    if commented_block.search(text):
        return commented_block.sub(desired, text, count=1)
    if active_block.search(text):
        return active_block.sub(desired, text, count=1)
    raise SystemExit("wrangler.toml is missing the KV namespace block")


def normalize_template(text: str) -> str:
    return replace_kv_binding(replace_name(text, WORKER_NAME_PLACEHOLDER), KV_NAMESPACE_ID_PLACEHOLDER)


def render_runtime_config(text: str) -> str:
    worker_name = require_env("CF_WORKER_NAME")
    kv_namespace_id = require_env("CF_KV_NAMESPACE_ID")
    template = normalize_template(text)
    return replace_kv_binding(replace_name(template, worker_name), kv_namespace_id)


def write_if_changed(path: Path, content: str) -> bool:
    final_content = content + ("\n" if not content.endswith("\n") else "")
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    if previous == final_content:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(final_content, encoding="utf-8")
    return True


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Sanitize tracked wrangler.toml or render a runtime-only config from secrets."
    )
    parser.add_argument(
        "mode",
        nargs="?",
        choices=("sanitize", "render"),
        default="sanitize",
        help="sanitize tracked wrangler.toml placeholders, or render a runtime-only config file",
    )
    parser.add_argument("--input", default=str(WRANGLER_PATH), help="source wrangler template path")
    parser.add_argument(
        "--output",
        help="output path for render mode; defaults to wrangler.runtime.toml at repo root",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    input_path = Path(args.input)
    text = input_path.read_text(encoding="utf-8")

    if args.mode == "sanitize":
        changed = write_if_changed(input_path, normalize_template(text))
        print("sanitized tracked wrangler.toml" if changed else "tracked wrangler.toml already sanitized")
        return 0

    output_path = Path(args.output or "wrangler.runtime.toml")
    changed = write_if_changed(output_path, render_runtime_config(text))
    print(f"rendered runtime wrangler config at {output_path}" if changed else f"runtime wrangler config already up to date at {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())