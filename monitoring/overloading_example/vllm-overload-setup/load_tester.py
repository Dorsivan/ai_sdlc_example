#!/usr/bin/env python3
"""
vLLM VRAM Overload Tester

This script sends concurrent requests to a vLLM endpoint to intentionally
overload GPU VRAM by filling the KV cache with multiple long-context requests.

Supports authentication via --api-key flag (sent as Authorization: Bearer header).
"""

import asyncio
import aiohttp
import argparse
import time
from typing import List
import json


class VRAMOverloadTester:
    def __init__(self, base_url: str, model: str = "TinyLlama/TinyLlama-1.1B-Chat-v1.0", api_key: str = None, use_chat_api: bool = False):
        self.base_url = base_url.rstrip('/')
        self.model = model
        self.api_key = api_key
        self.use_chat_api = use_chat_api

        # Choose API endpoint based on mode
        if use_chat_api:
            self.endpoint = f"{self.base_url}/v1/chat/completions"
        else:
            self.endpoint = f"{self.base_url}/v1/completions"

    def generate_long_prompt(self, size: int = 2000) -> str:
        """Generate a long prompt to consume KV cache slots."""
        base_text = (
            "You are a helpful AI assistant. Please analyze the following text "
            "in great detail and provide comprehensive insights. "
        )
        # Repeat to make it long
        filler = "The quick brown fox jumps over the lazy dog. " * (size // 10)
        return base_text + filler + "\n\nPlease provide a detailed analysis."

    async def send_request(self, session: aiohttp.ClientSession, request_id: int,
                          prompt_length: int = 2000, max_tokens: int = 512) -> dict:
        """Send a single inference request."""
        prompt = self.generate_long_prompt(prompt_length)

        # Build payload based on API type
        if self.use_chat_api:
            # Chat completions API format
            payload = {
                "model": self.model,
                "messages": [
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": False,
            }
        else:
            # Legacy completions API format
            payload = {
                "model": self.model,
                "prompt": prompt,
                "max_tokens": max_tokens,
                "temperature": 0.7,
                "top_p": 0.9,
                "stream": False,
            }

        # Prepare headers
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        start_time = time.time()
        try:
            async with session.post(self.endpoint, json=payload, headers=headers) as response:
                result = await response.json()
                elapsed = time.time() - start_time

                status = "SUCCESS" if response.status == 200 else "FAILED"
                print(f"[Request {request_id:3d}] {status} - {elapsed:.2f}s - Status: {response.status}")

                return {
                    "request_id": request_id,
                    "status": response.status,
                    "elapsed": elapsed,
                    "success": response.status == 200,
                    "response": result if response.status == 200 else None,
                    "error": result if response.status != 200 else None
                }
        except Exception as e:
            elapsed = time.time() - start_time
            print(f"[Request {request_id:3d}] ERROR - {elapsed:.2f}s - {str(e)}")
            return {
                "request_id": request_id,
                "status": -1,
                "elapsed": elapsed,
                "success": False,
                "error": str(e)
            }

    async def run_concurrent_load(self, num_requests: int = 50,
                                  concurrency: int = 10,
                                  prompt_length: int = 2000,
                                  max_tokens: int = 512) -> List[dict]:
        """Run concurrent requests to overload VRAM."""
        print(f"\n{'='*70}")
        print(f"Starting VRAM Overload Test")
        print(f"{'='*70}")
        print(f"Target URL:       {self.base_url}")
        print(f"Model:            {self.model}")
        print(f"Total Requests:   {num_requests}")
        print(f"Concurrency:      {concurrency}")
        print(f"Prompt Length:    ~{prompt_length} tokens")
        print(f"Max Tokens:       {max_tokens}")
        print(f"{'='*70}\n")

        connector = aiohttp.TCPConnector(limit=concurrency)
        timeout = aiohttp.ClientTimeout(total=300)  # 5 minute timeout

        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            # Create semaphore to limit concurrency
            semaphore = asyncio.Semaphore(concurrency)

            async def bounded_request(req_id: int):
                async with semaphore:
                    return await self.send_request(session, req_id, prompt_length, max_tokens)

            # Launch all requests
            tasks = [bounded_request(i) for i in range(num_requests)]
            results = await asyncio.gather(*tasks)

        return results

    def print_summary(self, results: List[dict]):
        """Print summary statistics."""
        total = len(results)
        successful = sum(1 for r in results if r['success'])
        failed = total - successful

        if successful > 0:
            avg_time = sum(r['elapsed'] for r in results if r['success']) / successful
        else:
            avg_time = 0

        print(f"\n{'='*70}")
        print(f"Test Summary")
        print(f"{'='*70}")
        print(f"Total Requests:     {total}")
        print(f"Successful:         {successful} ({successful/total*100:.1f}%)")
        print(f"Failed:             {failed} ({failed/total*100:.1f}%)")
        print(f"Avg Response Time:  {avg_time:.2f}s")
        print(f"{'='*70}\n")

        # Show error breakdown
        if failed > 0:
            print("Error Breakdown:")
            error_counts = {}
            for r in results:
                if not r['success']:
                    error_key = str(r.get('error', 'Unknown'))[:100]
                    error_counts[error_key] = error_counts.get(error_key, 0) + 1

            for error, count in sorted(error_counts.items(), key=lambda x: -x[1]):
                print(f"  [{count:3d}] {error}")
            print()


async def continuous_load(tester: VRAMOverloadTester, duration_seconds: int = 300,
                         concurrency: int = 20, prompt_length: int = 3000):
    """Run continuous load for a specified duration to sustain VRAM pressure."""
    print(f"\nStarting continuous load test for {duration_seconds} seconds...")
    print(f"This will maintain {concurrency} concurrent requests at all times.\n")

    start_time = time.time()
    request_id = 0
    active_tasks = set()

    connector = aiohttp.TCPConnector(limit=concurrency * 2)
    timeout = aiohttp.ClientTimeout(total=300)

    async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
        while time.time() - start_time < duration_seconds:
            # Maintain concurrency level
            while len(active_tasks) < concurrency:
                task = asyncio.create_task(
                    tester.send_request(session, request_id, prompt_length, 512)
                )
                active_tasks.add(task)
                request_id += 1

            # Wait for any task to complete
            done, active_tasks = await asyncio.wait(
                active_tasks,
                return_when=asyncio.FIRST_COMPLETED
            )

            # Brief pause to prevent tight loop
            await asyncio.sleep(0.1)

        # Wait for remaining tasks
        if active_tasks:
            await asyncio.wait(active_tasks)

    elapsed = time.time() - start_time
    print(f"\nContinuous load test completed: {request_id} requests in {elapsed:.1f}s")
    print(f"Average rate: {request_id/elapsed:.2f} req/s")


def main():
    parser = argparse.ArgumentParser(
        description="vLLM VRAM Overload Tester",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    parser.add_argument(
        "--url",
        default="https://maas.apps.ocp.2msw7.sandbox205.opentlc.com/maas-demo-llm/qwen-05b",
        help="Base URL of the vLLM service"
    )
    parser.add_argument(
        "--model",
        default="TinyLlama/TinyLlama-1.1B-Chat-v1.0",
        help="Model name"
    )
    parser.add_argument(
        "--requests",
        type=int,
        default=50,
        help="Total number of requests"
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=20,
        help="Number of concurrent requests"
    )
    parser.add_argument(
        "--prompt-length",
        type=int,
        default=3000,
        help="Approximate prompt length in tokens"
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=512,
        help="Maximum tokens to generate"
    )
    parser.add_argument(
        "--continuous",
        action="store_true",
        help="Run continuous load instead of fixed number of requests"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=300,
        help="Duration in seconds for continuous mode"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API key for authentication (sent as 'Authorization: Bearer <key>')"
    )
    parser.add_argument(
        "--chat-api",
        action="store_true",
        help="Use /v1/chat/completions endpoint instead of /v1/completions"
    )

    args = parser.parse_args()

    tester = VRAMOverloadTester(args.url, args.model, args.api_key, args.chat_api)

    if args.continuous:
        asyncio.run(
            continuous_load(
                tester,
                args.duration,
                args.concurrency,
                args.prompt_length
            )
        )
    else:
        results = asyncio.run(
            tester.run_concurrent_load(
                args.requests,
                args.concurrency,
                args.prompt_length,
                args.max_tokens
            )
        )
        tester.print_summary(results)


if __name__ == "__main__":
    main()
