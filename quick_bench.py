#!/usr/bin/env python3
"""Quick latency benchmark for top CTF models - 1 trial each."""
import asyncio, json, time
from openai import AsyncOpenAI

import os
API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
client = AsyncOpenAI(api_key=API_KEY, base_url="https://integrate.api.nvidia.com/v1")

PROMPT = "Analyze this binary: 1010 & 0110 = ? Explain step by step, then give answer."
MODELS = [
    ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B"),
    ("meta/llama-3.1-70b-instruct", "Llama 3.1 70B"),
    ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B"),
    ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick"),
    ("deepseek-ai/deepseek-v4-flash", "DeepSeek V4 Flash"),
    ("deepseek-ai/deepseek-v4-pro", "DeepSeek V4 Pro"),
    ("microsoft/phi-4-mini-instruct", "Phi-4 Mini"),
    ("google/gemma-4-31b-it", "Gemma 4 31B"),
    ("nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B"),
]

async def test(model_id, label):
    try:
        start = time.time()
        first_token_s = 0
        total_tokens = 0
        first = True
        stream = await client.chat.completions.create(
            model=model_id,
            messages=[{"role": "user", "content": PROMPT}],
            max_tokens=200, temperature=0.1, stream=True,
        )
        async for chunk in stream:
            if first and chunk.choices[0].delta.content:
                first_token_s = time.time() - start
                first = False
            if chunk.choices[0].delta.content:
                total_tokens += 1
        elapsed = time.time() - start
        tok_s = round(total_tokens / elapsed, 1) if elapsed > 0 else 0
        return {"model": model_id, "label": label, "total_s": round(elapsed, 3), "ttft_ms": round(first_token_s * 1000, 1), "tokens": total_tokens, "tok_s": tok_s}
    except Exception as e:
        return {"model": model_id, "label": label, "error": str(e)}

async def main():
    results = []
    for mid, label in MODELS:
        print(f"Testing {label}...", end=" ", flush=True)
        r = await test(mid, label)
        if "error" in r:
            print(f"ERROR: {r['error'][:60]}")
        else:
            print(f"{r['total_s']}s (TTFT={r['ttft_ms']}ms, {r['tok_s']} tok/s)")
        results.append(r)
        await asyncio.sleep(2)

    print("\n\n=== RESULTS ===")
    print(f"{'Rank':>4} {'Model':30s} {'Total(s)':>10} {'TTFT(ms)':>10} {'tok/s':>8}")
    print("-" * 70)
    valid = [r for r in results if "error" not in r]
    valid.sort(key=lambda r: r["total_s"])
    for rank, r in enumerate(valid, 1):
        print(f"{rank:>4} {r['label']:30s} {r['total_s']:>10.3f} {r['ttft_ms']:>10.1f} {r['tok_s']:>8.1f}")

    with open("/home/kali/Desktop/CTF/ctfagent/data/model_benchmark.json", "w") as f:
        json.dump(results, f, indent=2)

asyncio.run(main())
