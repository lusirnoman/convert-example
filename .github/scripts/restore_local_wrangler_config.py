#!/usr/bin/env python3
import os
import re
import sys
from pathlib import Path

WRANGLER_PATH = Path("wrangler.toml")


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


def main() -> int:
    worker_name = require_env("CF_WORKER_NAME")
    kv_namespace_id = require_env("CF_KV_NAMESPACE_ID")

    text = WRANGLER_PATH.read_text(encoding="utf-8")
    updated = replace_kv_binding(replace_name(text, worker_name), kv_namespace_id)

    if updated != text:
        WRANGLER_PATH.write_text(updated + ("\n" if not updated.endswith("\n") else ""), encoding="utf-8")
        print("updated wrangler.toml")
    else:
        print("wrangler.toml already matches configured secrets")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
