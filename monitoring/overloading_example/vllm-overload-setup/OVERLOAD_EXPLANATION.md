# How vLLM VRAM Overload Actually Works

This document explains the exact mechanism by which this test setup causes GPU VRAM overload.

## The Setup

- **Model**: TinyLlama-1.1B-Chat (~1.1GB weights)
- **GPU Memory Utilization**: 30% (low initial allocation)
- **Max Model Length**: 8192 tokens (large context window)
- **Max Num Seqs**: 128 concurrent sequences
- **Swap Space**: 0 (no CPU offloading - CRITICAL)

## VRAM Allocation in vLLM

When vLLM starts, it allocates VRAM in two main categories:

### 1. Model Weights (Static)
```
TinyLlama 1.1B parameters × 2 bytes (FP16) ≈ 2.2 GB
With optimizations (GPTQ, etc.): ~1.5 GB
```
This is **fixed** - doesn't change during inference.

### 2. KV Cache (Dynamic)
The `--gpu-memory-utilization=0.30` parameter tells vLLM:
> "Reserve 30% of available GPU VRAM for KV cache blocks"

On a 16GB GPU:
```
Total VRAM:              16 GB
Model weights:           -1.5 GB
Other overhead:          -0.5 GB
Available:               14 GB

30% for KV cache:        14 GB × 0.30 = 4.2 GB
```

vLLM pre-allocates this as **KV cache blocks** (chunks of memory for storing attention keys/values).

## How Requests Consume KV Cache

When a request comes in, vLLM allocates KV cache blocks to store:
- **Keys** (K) for each attention head
- **Values** (V) for each attention head
- For **every token** in the prompt + generation

### Memory per Token
For TinyLlama (simplified calculation):
```
Per token KV memory = num_heads × head_dim × 2 (K+V) × 2 bytes (FP16)
                    = 32 heads × 64 dims × 2 × 2 bytes
                    = 8,192 bytes
                    ≈ 8 KB per token
```

### Memory per Request
A request with a 4000-token prompt:
```
4000 tokens × 8 KB/token = 32 MB per request
```

A request with a 6000-token prompt:
```
6000 tokens × 8 KB/token = 48 MB per request
```

## The Overload Mechanism

### Scenario: 30 Concurrent Requests with 5000-Token Prompts

**Step 1: Calculate total KV cache needed**
```
30 requests × 5000 tokens × 8 KB/token = 1.2 GB
```

**Step 2: Compare to allocated KV cache**
```
Allocated KV cache:  4.2 GB
Requests need:       1.2 GB
Status:              ✅ Fits easily
```

Wait, this should work! **Why does it overload?**

## The Real Overload Triggers

### Trigger 1: Batching Overhead
vLLM doesn't just allocate exactly what's needed. It allocates in **blocks** (typically 16 tokens per block) and pads for batching:
```
Actual allocation ≈ requested × 1.3 (fragmentation overhead)
30 requests × 40 MB × 1.3 = 1.56 GB
```

### Trigger 2: Generation Phase
Each request doesn't stop at the prompt - it **generates tokens**:
```
5000-token prompt + 512 generated tokens = 5512 tokens total
30 requests × 5512 tokens × 8 KB = 1.3 GB → × 1.3 overhead = 1.7 GB
```

### Trigger 3: Request Queueing
With `max-num-seqs=128`, vLLM can queue many requests. If we send 50+ requests:
```
First 30 get KV cache:     1.7 GB
Next 20 get queued, but vLLM may pre-allocate blocks
Queued requests:           20 × 40 MB × 0.5 (partial) = 400 MB
Total:                     2.1 GB
```

### Trigger 4: The Continuous Load Test
The `continuous` mode in the load tester maintains a **constant 30 concurrent requests**:

```python
while time.time() - start_time < duration_seconds:
    while len(active_tasks) < concurrency:  # Refill to 30
        task = create_new_request()
        active_tasks.add(task)
```

As requests complete, new ones immediately replace them. This means:
- **No KV cache is freed** (new requests arrive before old ones release memory)
- vLLM's memory pool stays at maximum capacity
- **Steady-state overload** is maintained

### Trigger 5: Long-Running Generations
Some requests may generate longer outputs (up to `max_tokens=512`). These hold KV cache longer:
```
Request 1: Generates 512 tokens in 15 seconds
Request 2: Generates 150 tokens in 4 seconds

Request 1 holds 40% more KV cache for 375% longer!
```

## The Critical Role of `swap-space=0`

Without this parameter, vLLM would:
1. Detect VRAM exhaustion
2. Offload old KV cache blocks to CPU RAM
3. Continue serving requests (slower, but no errors)

**With `swap-space=0`:**
1. Detect VRAM exhaustion
2. ❌ No CPU offload available
3. **Reject new requests** or **OOM error**

This forces the **observable overload** we want to trigger alerts.

## Why Small Model + Low Utilization is Better

### Approach 1: Large Model + High Utilization (BAD)
```
Llama-2-7B at 95% utilization:
- Starts already near capacity
- Little room for KV cache growth
- Hard to observe the transition
- May OOM on startup
```

### Approach 2: Small Model + Low Utilization (GOOD)
```
TinyLlama at 30% utilization:
- Clear low baseline
- Plenty of room to observe KV cache growth
- Gradual transition: Low → Medium → HIGH → OVERLOAD
- Can tune the exact threshold by adjusting utilization %
```

## Expected Behavior Under Overload

### Metrics You'll See
```
# Before load test
vllm:kv_cache_usage_perc: 0.01-0.05  (1-5% - almost empty)
vllm:num_requests_running: 0
vllm:num_requests_waiting: 0
DCGM_FI_DEV_FB_USED: 1500-2000 MB   (model weights only)

# During moderate load (15 concurrent, 3000 tokens)
vllm:kv_cache_usage_perc: 0.40-0.60  (40-60% - comfortable)
vllm:num_requests_running: 15
vllm:num_requests_waiting: 0-2
DCGM_FI_DEV_FB_USED: 2500-3500 MB

# During OVERLOAD (30 concurrent, 5000 tokens, sustained)
vllm:kv_cache_usage_perc: 0.90-1.00  (90-100% - FULL!)
vllm:num_requests_running: 8-12      (reduced throughput)
vllm:num_requests_waiting: 18-25+    (large queue)
DCGM_FI_DEV_FB_USED: 4500-5500 MB   (at capacity)

# Errors you may see:
HTTP 503: Service Unavailable
HTTP 500: Out of memory
Logs: "No available KV cache blocks"
```

### Why Throughput Drops
When KV cache is exhausted:
1. vLLM can't start new requests (no free blocks)
2. Only running requests continue
3. When a request finishes, its blocks are freed
4. Next queued request immediately grabs those blocks
5. **Steady state**: Lower throughput, high queue depth

## Summary

The overload happens because:
1. **Small allocated KV cache** (30% of VRAM)
2. **Large prompt sizes** (5000-6000 tokens)
3. **High concurrency** (30+ simultaneous requests)
4. **Continuous pressure** (new requests arrive as fast as old ones finish)
5. **No escape valve** (`swap-space=0` prevents CPU offloading)

Result: KV cache fills to 95-100%, VRAM exhausted, requests queue or fail → **Alert triggers!** 🚨
