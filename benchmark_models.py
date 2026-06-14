#!/usr/bin/env python3
"""Benchmark NVIDIA NIM models for latency and throughput."""
import asyncio
import json
import time
import statistics
from openai import AsyncOpenAI

import os
API_KEY = os.environ.get("NVIDIA_NIM_API_KEY", "")
BASE_URL = os.environ.get("NVIDIA_NIM_BASE_URL", "https://integrate.api.nvidia.com/v1")

client = AsyncOpenAI(api_key=API_KEY, base_url=BASE_URL)

# Test prompts of increasing complexity
PROMPTS = {
    "short": "What is 2+2?",
    "medium": "Write a Python function to solve a binary operation like '1010 & 0110'. Return just the code.",
    "long": "Analyze this CTF challenge: The server at host:port asks binary operation questions. "
            "You need to connect, read the prompt, compute the answer, and send it back. "
            "Write a complete solution strategy with step-by-step instructions.",
}

# Models to benchmark - focus on text generation suitable for CTF
MODELS = [
    # Current models (baseline)
    ("meta/llama-3.1-8b-instruct", "Llama 3.1 8B", "current"),
    ("meta/llama-3.1-70b-instruct", "Llama 3.1 70B", "current"),
    # Newer Llama
    ("meta/llama-3.3-70b-instruct", "Llama 3.3 70B", "newer"),
    ("meta/llama-4-maverick-17b-128e-instruct", "Llama 4 Maverick 17B", "newest"),
    ("meta/llama-3.2-3b-instruct", "Llama 3.2 3B", "small"),
    # DeepSeek
    ("deepseek-ai/deepseek-v4-flash", "DeepSeek V4 Flash", "fast"),
    ("deepseek-ai/deepseek-v4-pro", "DeepSeek V4 Pro", "powerful"),
    # Mistral
    ("mistralai/mistral-large", "Mistral Large", "powerful"),
    # Google
    ("google/gemma-4-31b-it", "Gemma 4 31B", "google"),
    ("google/gemma-3-12b-it", "Gemma 3 12B", "google"),
    # Microsoft
    ("microsoft/phi-4-mini-instruct", "Phi-4 Mini", "small"),
    # NVIDIA optimized
    ("nvidia/llama-3.3-nemotron-super-49b-v1", "Nemotron Super 49B", "nvidia"),
]

async def benchmark_model(model_id: str, label: str, category: str) -> dict:
    results = {"model": model_id, "label": label, "category": category, "prompts": {}}

    for prompt_name, prompt_content in PROMPTS.items():
        latencies = []
        tokens_per_sec = []
        ttft_values = []  # time-to-first-token

        for trial in range(2):
            try:
                # Measure time-to-first-token + total time via streaming
                start = time.time()
                first_token = True
                total_tokens = 0
                first_token_time = 0

                stream = await client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt_content}],
                    max_tokens=128,
                    temperature=0.1,
                    stream=True,
                )

                async for chunk in stream:
                    if first_token and chunk.choices[0].delta.content:
                        first_token_time = time.time() - start
                        first_token = False
                    if chunk.choices[0].delta.content:
                        total_tokens += 1

                elapsed = time.time() - start
                latencies.append(elapsed)
                ttft_values.append(first_token_time)
                if total_tokens > 0:
                    tokens_per_sec.append(total_tokens / elapsed)
                else:
                    tokens_per_sec.append(0)

            except Exception as e:
                print(f"  Error {model_id}/{prompt_name} trial {trial}: {e}")
                latencies.append(None)
                ttft_values.append(None)
                tokens_per_sec.append(None)

        valid = [(l, t, tp) for l, t, tp in zip(latencies, ttft_values, tokens_per_sec) if l is not None]
        if valid:
            lats, ttfts, tpss = zip(*valid)
            results["prompts"][prompt_name] = {
                "avg_latency_s": round(statistics.mean(lats), 3),
                "min_latency_s": round(min(lats), 3),
                "avg_ttft_s": round(statistics.mean(ttfts), 3),
                "avg_tokens_per_sec": round(statistics.mean(tpss), 1),
            }
        else:
            results["prompts"][prompt_name] = {"error": "all trials failed"}

    # Overall score (lower is better - weighted by prompt complexity)
    scores = []
    for pname in ["short", "medium", "long"]:
        pdata = results["prompts"].get(pname, {})
        if "avg_latency_s" in pdata:
            # Weight: short=1x, medium=2x, long=3x
            weight = {"short": 1, "medium": 2, "long": 3}[pname]
            scores.append(pdata["avg_latency_s"] * weight)

    if scores:
        results["weighted_score"] = round(sum(scores) / sum({"short": 1, "medium": 2, "long": 3}[p] for p in PROMPTS), 3)

    print(f"  {label:40s} | short={results['prompts'].get('short',{}).get('avg_latency_s','ERR'):>6} | medium={results['prompts'].get('medium',{}).get('avg_latency_s','ERR'):>6} | long={results['prompts'].get('long',{}).get('avg_latency_s','ERR'):>6}")
    return results


async def main():
    print(f"{'Model':40s} | {'Short':>6} | {'Medium':>6} | {'Long':>6}")
    print("-" * 70)

    all_results = []
    for model_id, label, category in MODELS:
        print(f"Benchmarking {label} ({model_id})...")
        result = await benchmark_model(model_id, label, category)
        all_results.append(result)

    # Sort by weighted score
    all_results.sort(key=lambda r: r.get("weighted_score", 999))

    print("\n\n=== OVERALL RANKING (by weighted latency) ===")
    print(f"{'Rank':>4} {'Model':40s} {'Category':15s} {'Score':>8} {'Short(s)':>10} {'Medium(s)':>10} {'Long(s)':>10} {'TTFT(ms)':>10} {'tok/s':>8}")
    print("-" * 120)
    for rank, r in enumerate(all_results, 1):
        s = r.get("prompts", {})
        score = r.get("weighted_score", "N/A")
        short_lat = s.get("short", {}).get("avg_latency_s", "N/A")
        med_lat = s.get("medium", {}).get("avg_latency_s", "N/A")
        long_lat = s.get("long", {}).get("avg_latency_s", "N/A")
        ttft = s.get("short", {}).get("avg_ttft_s", "N/A")
        if isinstance(ttft, (int, float)):
            ttft = round(ttft * 1000, 1)  # convert to ms
        tps = s.get("medium", {}).get("avg_tokens_per_sec", "N/A")
        print(f"{rank:>4} {r['label']:40s} {r['category']:15s} {str(score):>8} {str(short_lat):>10} {str(med_lat):>10} {str(long_lat):>10} {str(ttft):>10} {str(tps):>8}")

    print("\n\n=== RECOMMENDATION ===")
    if all_results:
        best = all_results[0]
        print(f"Fastest: {best['label']} ({best['model']}) - score={best.get('weighted_score', 'N/A')}")
        if len(all_results) > 1:
            second = all_results[1]
            print(f"Runner-up: {second['label']} ({second['model']}) - score={second.get('weighted_score', 'N/A')}")

    # Save full results
    with open("/home/kali/Desktop/CTF/ctfagent/data/model_benchmark.json", "w") as f:
        json.dump(all_results, f, indent=2)
    print("\nFull results saved to data/model_benchmark.json")


if __name__ == "__main__":
    asyncio.run(main())
