# MaaS Token Drift Debugging

Since you have `include_usage` enabled and are comparing `total_tokens`, check the gateway logs for dropped token counts:

```bash
oc logs -n openshift-ingress -l gateway.networking.k8s.io/gateway-name=maas-default-gateway -c istio-proxy | grep "Missing json property" | wc -l
```

Each occurrence is a request where the wasm-shim couldn't parse `/usage/total_tokens` from the response and reported 0 tokens. This warning occurs even on confirmed clusters. If the count matches your drift, that's the cause.

If zero occurrences, enable `usageLogging` and compare per-request OTel logs against what your code receives to pinpoint the mismatch.
