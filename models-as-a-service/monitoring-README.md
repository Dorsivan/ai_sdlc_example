# LLM Inference Service Monitoring

This directory contains monitoring configurations for the LLMInferenceService components.

## Components Monitored

### 1. vLLM Metrics (`servicemonitor-vllm.yaml`)
- **Target**: Inference pods running vLLM
- **Port**: 8000 (https)
- **Path**: `/metrics`
- **Metrics include**:
  - Request latency
  - Throughput (tokens/sec)
  - GPU utilization
  - KV cache usage
  - Queue depth

### 2. llm-d Scheduler Metrics (`servicemonitor-llmd.yaml` and `podmonitor-llmd.yaml`)
- **Target**: llm-d scheduler/router component
- **Metrics include**:
  - Endpoint selection decisions
  - Queue scorer metrics
  - KV cache utilization scorer
  - Prefix cache scorer
  - Routing latency

## Deployment

### Option 1: Deploy all monitoring components
```bash
oc apply -f servicemonitor-vllm.yaml
oc apply -f servicemonitor-llmd.yaml
oc apply -f podmonitor-llmd.yaml
```

### Option 2: Deploy only specific monitors
For vLLM only:
```bash
oc apply -f servicemonitor-vllm.yaml
```

For llm-d scheduler only:
```bash
# Try ServiceMonitor first
oc apply -f servicemonitor-llmd.yaml

# If ServiceMonitor doesn't work, use PodMonitor
oc apply -f podmonitor-llmd.yaml
```

## Verification

### 1. Check ServiceMonitor/PodMonitor status
```bash
oc get servicemonitor -n demo-llm
oc get podmonitor -n demo-llm
```

### 2. Verify target discovery in Prometheus
Access Prometheus UI and check:
- Status → Targets
- Look for `demo-llm/llm-vllm-metrics` and `demo-llm/llm-scheduler-metrics`

### 3. Query metrics
Example PromQL queries:

**vLLM metrics:**
```promql
# Request rate
rate(vllm:request_success_total[5m])

# Average latency
rate(vllm:request_duration_seconds_sum[5m]) / rate(vllm:request_duration_seconds_count[5m])

# GPU memory usage
vllm:gpu_cache_usage_perc
```

**llm-d scheduler metrics:**
```promql
# Routing decisions
rate(llmd_scheduler_route_total[5m])

# Queue depth
llmd_scheduler_queue_depth

# Endpoint selection latency
histogram_quantile(0.95, rate(llmd_scheduler_selection_duration_bucket[5m]))
```

### 4. Verify Service labels
Check that the KServe-created Services have the expected labels:
```bash
oc get svc -n demo-llm -l serving.kserve.io/inferenceservice=gpt-oss-20b --show-labels
```

### 5. Check Service ports
Verify port names match the ServiceMonitor configuration:
```bash
oc get svc -n demo-llm -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.ports[*].name}{"\n"}{end}'
```

## Troubleshooting

### Metrics not appearing in Prometheus

1. **Check ServiceMonitor is created**:
   ```bash
   oc describe servicemonitor llm-vllm-metrics -n demo-llm
   ```

2. **Verify selector matches Service labels**:
   ```bash
   oc get svc -n demo-llm -l serving.kserve.io/inferenceservice=gpt-oss-20b
   ```

3. **Check Prometheus operator logs**:
   ```bash
   oc logs -n openshift-monitoring -l app.kubernetes.io/name=prometheus-operator
   ```

4. **Test metrics endpoint directly**:
   ```bash
   # Port-forward to the inference pod
   oc port-forward -n demo-llm pod/<pod-name> 8000:8000
   
   # Query metrics (skip TLS verification)
   curl -k https://localhost:8000/metrics
   ```

### Adjust port names

If the port names don't match, update the ServiceMonitor:
```bash
# Find actual port names
oc get svc -n demo-llm <service-name> -o yaml | grep -A5 ports:

# Update the ServiceMonitor's 'port:' field to match
```

## Metrics Reference

### Key vLLM Metrics
- `vllm:num_requests_running` - Currently executing requests
- `vllm:num_requests_waiting` - Queued requests
- `vllm:gpu_cache_usage_perc` - KV cache utilization
- `vllm:avg_generation_throughput_toks_per_s` - Token generation rate
- `vllm:request_duration_seconds` - Request latency histogram

### Key llm-d Metrics
- `llmd_scheduler_endpoints_total` - Available endpoints
- `llmd_scheduler_route_total` - Routing decisions
- `llmd_scheduler_queue_depth` - Pending requests per endpoint
- `llmd_scheduler_kv_cache_utilization` - Cache usage per endpoint
- `llmd_scheduler_selection_duration_seconds` - Routing decision latency
