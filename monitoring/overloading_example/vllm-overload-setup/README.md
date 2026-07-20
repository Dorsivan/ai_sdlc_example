# vLLM VRAM Overload Testing with LLMInferenceService

This directory contains a complete setup for intentionally overloading GPU VRAM in a vLLM deployment on OpenShift using the **LLMInferenceService** custom resource from llm-d/KServe.

## Testing Philosophy

Unlike starting at 95% GPU memory utilization, this setup uses a **realistic stress test workflow**:

1. **Deploy with minimal baseline** - Small model (TinyLlama 1.1B) + low gpu-memory-utilization (30%)
2. **Measure actual VRAM usage** - Observe how much the model itself consumes
3. **Load test to trigger overload** - Send concurrent long-context requests to push KV cache beyond the 30% limit
4. **Watch the transition** - See VRAM go from low → normal → **overloaded** in real-time

This approach lets you observe the actual progression into overload, rather than starting already at capacity.

## Components

### 1. LLMInferenceService Configuration (`inferenceservice.yaml`)
- **Model**: TinyLlama-1.1B-Chat (tiny ~1.1GB model for minimal baseline)
- **Key Settings**:
  - `gpu-memory-utilization: 0.30` - **Low initial allocation** (leaves room for KV cache growth)
  - `max-model-len: 8192` - **Large context window** (enables significant KV cache growth)
  - `max-num-seqs: 128` - Allows concurrent sequences
  - `swap-space: 0` - **CRITICAL**: No CPU offloading = hard OOM when VRAM exhausted

### 2. Load Testing Script (`load_tester.py`)
Python async script that:
- Sends concurrent requests to fill the KV cache
- Supports both burst and continuous load patterns
- Generates long prompts (up to 7000 tokens) to maximize KV cache allocation
- Provides detailed statistics and error reporting

### 3. Test Scenarios (`vllm-config.yaml`)
- ConfigMap with pre-defined test scenarios for different overload patterns

## How VRAM Overload Actually Happens

**📖 For a deep dive into the exact mechanisms, see [OVERLOAD_EXPLANATION.md](./OVERLOAD_EXPLANATION.md)**

The overload mechanism works through **KV cache exhaustion**:

### Step 1: Baseline (Low VRAM)
```
Model weights:           ~1.5 GB  (TinyLlama 1.1B)
GPU memory utilization:  30%
Available for KV cache:  ~4-5 GB  (on a typical 16GB GPU)
Status:                  ✅ Plenty of room
```

### Step 2: Load Test Starts
When you send concurrent requests with long prompts:

1. **Each request allocates KV cache blocks**
   - A 4000-token prompt requires ~4000 KV cache slots
   - Each slot stores key/value tensors for all attention heads
   - For TinyLlama: ~4000 tokens × 32 heads × 64 dims × 2 (K+V) × 2 bytes (fp16) ≈ 32MB per request

2. **Concurrent requests multiply the pressure**
   - 20 concurrent requests × 32MB each = **640MB just for KV cache**
   - vLLM pre-allocates KV cache blocks based on `gpu-memory-utilization`
   - With only 30% allocated, you have ~4-5GB for KV cache

3. **The math works against you**
   - At 30% utilization with 128 max sequences, vLLM allocates KV blocks
   - Load tester sends 50+ concurrent long requests
   - **KV cache fills up → requests queue → memory pressure builds**

### Step 3: Overload Triggered
```
Model weights:           ~1.5 GB  (unchanged)
KV cache filled:         ~4.5 GB  (at capacity!)
Queued requests:         30+      (waiting for KV cache blocks)
New request arrives:     ❌ NO FREE KV CACHE BLOCKS
swap-space=0:            ❌ CPU offload disabled
Result:                  🔥 OOM ERROR or request rejection
```

### Why `swap-space=0` is Critical
- **Without it**: vLLM would offload KV cache to CPU RAM, hiding the problem
- **With it**: Hard failure when GPU VRAM is exhausted → **observable overload**

### Why Long Prompts Matter
- Short prompt (100 tokens): ~0.8 MB KV cache per request
- Long prompt (4000 tokens): ~32 MB KV cache per request  
- **40x more memory pressure** with long contexts!

## Authentication

The load tester supports API key authentication via the `--api-key` flag:

```bash
# Pass API key directly
python3 load_tester.py \
  --url http://localhost:8080 \
  --api-key your-api-key-here \
  --requests 10 \
  --concurrency 5

# Or use environment variable
export VLLM_API_KEY="your-api-key-here"
python3 load_tester.py \
  --url http://localhost:8080 \
  --api-key $VLLM_API_KEY \
  --requests 10
```

The API key is sent as an `Authorization: Bearer <key>` header with each request.

**Note**: The default vLLM deployment doesn't require authentication. This is useful when:
- Testing against a production endpoint with auth enabled
- Using a gateway/proxy that requires authentication
- Testing through OpenShift routes with token requirements

## Step-by-Step Overload Testing Workflow

### Step 1: Deploy with Low Baseline
```bash
# Create namespace
oc create namespace vllm-test

# Deploy the service (starts at 30% GPU memory utilization)
oc apply -f inferenceservice.yaml
oc apply -f vllm-config.yaml

# Wait for deployment
oc wait --for=condition=ready pod -l serving.kserve.io/llminferenceservice=vllm-overload-test -n vllm-test --timeout=600s

# Check status
oc get llminferenceservice vllm-overload-test -n vllm-test
oc get pods -n vllm-test
```

### Step 2: Measure Baseline VRAM Usage
```bash
# Port forward to access metrics
oc port-forward -n vllm-test svc/vllm-overload-test 8080:8080

# In another terminal, check baseline VRAM
curl -s http://localhost:8080/metrics | grep DCGM_FI_DEV_FB

# Example output:
# DCGM_FI_DEV_FB_USED 2048    ← Model loaded, minimal KV cache
# DCGM_FI_DEV_FB_FREE 14336   ← Plenty of free VRAM

# Check KV cache utilization (should be near 0%)
curl -s http://localhost:8080/metrics | grep vllm:kv_cache_usage_perc

# Verify the service is responding
curl http://localhost:8080/v1/models
```

### Step 3: Gradually Increase Load to Trigger Overload
Now we'll send concurrent long-context requests to fill the KV cache beyond the 30% limit.

```bash
# Install dependencies
pip install aiohttp

# Port forward the service (if not already running)
oc port-forward -n vllm-test svc/vllm-overload-test 8080:8080

# Terminal 1: Watch VRAM metrics in real-time
watch -n 2 'curl -s http://localhost:8080/metrics | grep -E "(DCGM_FI_DEV_FB_USED|vllm:kv_cache_usage_perc|vllm:num_requests)"'

# Terminal 2: Start with light load
python3 load_tester.py \
  --url http://localhost:8080 \
  --requests 10 \
  --concurrency 5 \
  --prompt-length 2000

# If authentication is required, add --api-key:
# python3 load_tester.py --url http://localhost:8080 --api-key YOUR_API_KEY --requests 10 ...

# Observe: KV cache usage increases slightly, VRAM still low

# Terminal 2: Increase to moderate load
python3 load_tester.py \
  --url http://localhost:8080 \
  --requests 30 \
  --concurrency 15 \
  --prompt-length 4000

# Observe: KV cache filling up, VRAM climbing

# Terminal 2: Push to overload with aggressive load
python3 load_tester.py \
  --url http://localhost:8080 \
  --requests 50 \
  --concurrency 30 \
  --prompt-length 6000

# Observe: KV cache at capacity, requests queueing or failing, VRAM exhausted!

# Terminal 2: Sustained overload test
python3 load_tester.py \
  --url http://localhost:8080 \
  --continuous \
  --duration 300 \
  --concurrency 25 \
  --prompt-length 5000

# This maintains overload conditions for 5 minutes to trigger alerts
```

### What You Should See During Overload

**Metrics progression:**
```
# Baseline (no load)
DCGM_FI_DEV_FB_USED: 2048 MB          ← Model weights only
vllm:kv_cache_usage_perc: 0.02        ← Almost no KV cache used

# Light load (10 requests, 5 concurrent)
DCGM_FI_DEV_FB_USED: 2560 MB          ← +512 MB for KV cache
vllm:kv_cache_usage_perc: 0.15        ← 15% KV cache used
vllm:num_requests_running: 5          ← All requests running

# Moderate load (30 requests, 15 concurrent)  
DCGM_FI_DEV_FB_USED: 3840 MB          ← +1280 MB more KV cache
vllm:kv_cache_usage_perc: 0.65        ← 65% KV cache used
vllm:num_requests_running: 15         ← All requests running
vllm:num_requests_waiting: 3          ← Some queueing starts

# **OVERLOAD** (50 requests, 30 concurrent, long prompts)
DCGM_FI_DEV_FB_USED: 5120 MB+         ← KV cache exhausted!
vllm:kv_cache_usage_perc: 0.95-1.00   ← 95-100% KV cache full
vllm:num_requests_running: 8          ← Reduced throughput
vllm:num_requests_waiting: 22+        ← Large queue buildup
HTTP errors: 503 / OOM errors         ← Requests failing
```

### Alternative: Run from Inside Cluster
```bash
# Create a test pod
oc run vllm-tester -n vllm-test \
  --image=python:3.11-slim \
  --restart=Never \
  --rm -it \
  -- bash

# Inside the pod:
pip install aiohttp
# Copy load_tester.py to the pod
python3 load_tester.py \
  --url http://vllm-overload-test.vllm-test.svc.cluster.local:8080 \
  --requests 100 \
  --concurrency 30

# With authentication:
# python3 load_tester.py --url http://... --api-key $API_KEY --requests 100 --concurrency 30
```

### Alternative: Use Pre-defined Scenarios via Job
```bash
# Deploy a job that runs scenarios
cat <<EOF | oc apply -f -
apiVersion: batch/v1
kind: Job
metadata:
  name: vllm-load-test
  namespace: vllm-test
spec:
  template:
    spec:
      containers:
      - name: tester
        image: python:3.11-slim
        command: ["/bin/bash", "-c"]
        args:
          - |
            pip install aiohttp
            # Copy load_tester.py here
            export VLLM_URL=http://vllm-overload-test.vllm-test.svc.cluster.local:8080
            bash /scenarios/scenario1.sh
        volumeMounts:
        - name: scenarios
          mountPath: /scenarios
      volumes:
      - name: scenarios
        configMap:
          name: vllm-test-scenarios
          defaultMode: 0755
      restartPolicy: Never
  backoffLimit: 1
EOF
```

## Test Scenarios

### Scenario 1: Burst Load
- 100 requests with 50 concurrent
- 4000 token prompts
- Simulates sudden traffic spike

### Scenario 2: Long Context Stress
- 30 requests with 15 concurrent  
- 7000 token prompts
- Tests maximum context handling

### Scenario 3: Sustained Load
- Continuous for 10 minutes
- 25 concurrent requests
- 3000 token prompts
- Tests sustained VRAM pressure

### Scenario 4: High Frequency
- 200 requests with 40 concurrent
- Smaller 1500 token prompts
- Tests rapid KV cache allocation/deallocation

## Monitoring VRAM Usage

### Using Prometheus Metrics
The vLLM service exposes metrics at `/metrics`:

```bash
# View metrics
oc port-forward -n vllm-test svc/vllm-overload-test 8080:8080
curl http://localhost:8080/metrics | grep -E '(vllm_|gpu_)'
```

Key metrics to watch:
- `vllm:kv_cache_usage_perc` - KV cache utilization percentage
- `DCGM_FI_DEV_FB_USED` - GPU framebuffer memory used (MB)
- `DCGM_FI_DEV_FB_FREE` - GPU framebuffer memory free (MB)
- `vllm:num_requests_running` - Active requests
- `vllm:num_requests_waiting` - Queued requests

### Using NVIDIA Tools
```bash
# Exec into the pod
oc exec -it -n vllm-test <pod-name> -- bash

# Watch GPU utilization
watch nvidia-smi

# Detailed memory info
nvidia-smi -q -d MEMORY
```

## Triggering the GPU Memory Alert

Based on your `gpu-memory-alert-rule.yaml`, the alert triggers when:
```
DCGM_FI_DEV_FB_USED - (10220 + (8960 * vllm:kv_cache_usage_perc)) < 0
```

This means: **Available VRAM = Total Used - (Base Model + KV Cache)**

When this calculation becomes negative, VRAM is overloaded.

### Strategy to Trigger the Alert

**Goal**: Push `vllm:kv_cache_usage_perc` to 95%+ while maintaining high `DCGM_FI_DEV_FB_USED`

1. **Start with baseline** - Verify model is loaded, metrics are being scraped
2. **Ramp up gradually** - Light → Moderate → Aggressive load (see above)
3. **Sustain overload** - Run continuous test for 5+ minutes to exceed the 2-minute alert threshold
4. **Monitor the formula** - Watch for the calculation to go negative

**Recommended test sequence:**
```bash
# Port forward (Terminal 1)
oc port-forward -n vllm-test svc/vllm-overload-test 8080:8080

# Watch metrics (Terminal 2)
watch -n 2 'curl -s http://localhost:8080/metrics | grep -E "(DCGM_FI_DEV_FB_USED|vllm:kv_cache_usage_perc)" | head -5'

# Run sustained overload test (Terminal 3)
# This maintains high concurrency + long prompts for 10 minutes
python3 load_tester.py \
  --url http://localhost:8080 \
  --continuous \
  --duration 600 \
  --concurrency 30 \
  --prompt-length 5000

# After ~2-3 minutes of overload, the alert should fire
```

**What triggers the alert:**
- `vllm:kv_cache_usage_perc` reaches 0.95+ (95%+ KV cache full)
- `DCGM_FI_DEV_FB_USED` stays high (5GB+)
- The formula `DCGM_FI_DEV_FB_USED - (10220 + (8960 * 0.95))` becomes negative
- Condition persists for 2 minutes → **Alert fires** 🚨

## Tuning the Overload Threshold

The current setup should reliably overload with the aggressive test (50 requests, 30 concurrent, 6000 tokens). If you want to control **when** overload happens:

### Make Overload Happen Sooner (More Sensitive)
1. **Lower gpu-memory-utilization** (less KV cache headroom):
   ```yaml
   args:
     - --gpu-memory-utilization=0.20  # Only 20% for KV cache
   ```

2. **Reduce max-num-seqs** (less concurrent capacity):
   ```yaml
   args:
     - --max-num-seqs=64  # Half the concurrent sequence slots
   ```

3. **Use longer prompts in tests**:
   ```bash
   python3 load_tester.py --prompt-length 7000 --concurrency 20
   ```

### Make Overload Happen Later (Less Sensitive)
1. **Increase gpu-memory-utilization** (more KV cache headroom):
   ```yaml
   args:
     - --gpu-memory-utilization=0.50  # 50% for KV cache
   ```

2. **Use a smaller model** (leaves even more VRAM for KV cache):
   ```yaml
   # TinyLlama is already tiny, but you could try:
   uri: hf://facebook/opt-125m  # Even smaller 125M model
   ```

3. **Reduce test concurrency**:
   ```bash
   python3 load_tester.py --concurrency 10 --prompt-length 3000
   ```

### Why Not Just Use a Huge Model?
Using a small model (TinyLlama) with low gpu-memory-utilization gives you **fine-grained control**:
- You can observe the gradual VRAM increase as KV cache fills
- You can tune the exact overload threshold by adjusting gpu-memory-utilization
- The transition from normal → overloaded is clear and observable

With a huge model at 95% utilization, you start already near the limit and can't see the progression.

## Cleanup

```bash
# Delete the test resources
oc delete llminferenceservice vllm-overload-test -n vllm-test
oc delete configmap vllm-test-scenarios -n vllm-test
oc delete namespace vllm-test
```

## Troubleshooting

### Pod won't start / OOMKilled immediately
- The model is too large for available VRAM
- Check pod logs: `oc logs -n vllm-test <pod-name>`
- Reduce `--max-model-len` or use smaller model

### No VRAM pressure even with load
- Increase `--concurrency` and `--prompt-length`
- Verify KV cache metrics are increasing
- Check if GPU has more VRAM than expected

### Requests timing out
- vLLM may be queueing requests when VRAM is full
- This is expected behavior - monitor queue metrics
- Reduce `--max-num-seqs` to trigger failures faster

### Alert not firing
- Check Prometheus is scraping the pod
- Verify the metric calculation manually in Prometheus UI
- Ensure alert rule is deployed in correct namespace

## References

- [Understanding LLMInferenceService | KServe](https://kserve.github.io/website/docs/model-serving/generative-inference/llmisvc/llmisvc-overview)
- [LLMInferenceService Configuration Guide | KServe](https://kserve.github.io/website/docs/model-serving/generative-inference/llmisvc/llmisvc-configuration)
- [Red Hat AI Inference on Amazon EKS: Kubernetes resources](https://developers.redhat.com/articles/2026/06/16/red-hat-ai-inference-amazon-eks-kubernetes-resources)
- [Combining KServe and llm-d for optimized generative AI inference](https://developers.redhat.com/articles/2026/04/21/kserve-llm-d-optimized-gen-ai-inference)
