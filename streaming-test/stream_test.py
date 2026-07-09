#!/usr/bin/env python3
"""Test an OpenAI-compatible endpoint and stream the response tokens.

Works with vLLM / llm-d style servers (e.g. the gpt-oss-20b deployment).
Uses server-sent events (SSE) so tokens print as they arrive.

Usage:
    python stream_test.py --url http://localhost:8000 --model gpt-oss-20b \
        --prompt "Explain streaming in one sentence."

Environment variables (used as defaults):
    ENDPOINT_URL   base URL, e.g. http://localhost:8000
    MODEL_NAME     model id, e.g. gpt-oss-20b
    API_KEY        bearer token (optional)
"""
import argparse
import json
import os
import sys
import time

import requests


def stream_chat(base_url, model, prompt, api_key=None, timeout=60):
    url = base_url.rstrip("/") + "/v1/chat/completions"
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": True,
        # ask the server to include usage stats in the final chunk
        "stream_options": {"include_usage": True},
    }

    print(f"POST {url}")
    print(f"model={model!r}  prompt={prompt!r}\n")
    print("--- streamed response ---")

    started = time.time()
    first_token_at = None
    token_count = 0
    usage = None

    with requests.post(
        url, headers=headers, json=payload, stream=True, timeout=timeout
    ) as resp:
        resp.raise_for_status()
        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:  # keep-alive blank line between events
                continue
            if not raw.startswith("data:"):
                continue
            data = raw[len("data:"):].strip()
            if data == "[DONE]":
                break
            try:
                chunk = json.loads(data)
            except json.JSONDecodeError:
                print(f"\n[warn] could not parse chunk: {data!r}", file=sys.stderr)
                continue

            if chunk.get("usage"):
                usage = chunk["usage"]

            for choice in chunk.get("choices", []):
                delta = choice.get("delta", {})
                piece = delta.get("content")
                if piece:
                    if first_token_at is None:
                        first_token_at = time.time()
                    token_count += 1
                    print(piece, end="", flush=True)

    elapsed = time.time() - started
    print("\n\n--- stats ---")
    if first_token_at is not None:
        print(f"time to first token: {first_token_at - started:.3f}s")
    print(f"total time:          {elapsed:.3f}s")
    print(f"content chunks:      {token_count}")
    if usage:
        print(f"usage:               {usage}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=os.environ.get(
            "ENDPOINT_URL",
            "http://a61320ff97c734ff49798c5d76421dd0-2008927439.us-east-1.elb.amazonaws.com/demo-llm/gpt-oss-20b",
        ),
        help="Base URL of the endpoint (default: $ENDPOINT_URL or the demo-llm gpt-oss-20b LB)",
    )
    parser.add_argument(
        "--model",
        default=os.environ.get("MODEL_NAME", "gpt-oss-20b"),
        help="Model id (default: $MODEL_NAME or gpt-oss-20b)",
    )
    parser.add_argument(
        "--prompt",
        default="Explain what token streaming is in one sentence.",
        help="Prompt to send",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("API_KEY", "sk-oai-Q3co4wTvCwUJYDOI_4yV4EfrAXpjRezyP20RLMYHvt2An2WcTHOWftLtz7jp"),
        help="Bearer token (default: $API_KEY)",
    )
    parser.add_argument("--timeout", type=int, default=60)
    args = parser.parse_args()

    try:
        stream_chat(
            args.url, args.model, args.prompt,
            api_key=args.api_key, timeout=args.timeout,
        )
    except requests.exceptions.HTTPError as e:
        print(f"\n[error] HTTP {e.response.status_code}: {e.response.text}", file=sys.stderr)
        sys.exit(1)
    except requests.exceptions.RequestException as e:
        print(f"\n[error] request failed: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
