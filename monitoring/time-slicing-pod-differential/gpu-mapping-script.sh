#!/bin/bash

# Output JSON format for Prometheus exporter
# Format: {"pid": "123", "namespace": "default", "pod": "pod-name", "gpu_id": "0", "gpu_memory_mb": "1024", "node": "node-1"}

OUTPUT_FILE="/tmp/gpu_metrics.json"
NODE_NAME=${NODE_NAME:-$(hostname)}

echo "[" > "$OUTPUT_FILE"

# Grab all currently active GPU processes with GPU ID and memory
nvidia_output=$(nvidia-smi --query-compute-apps=pid,used_gpu_memory,gpu_uuid --format=csv,noheader,nounits 2>/dev/null)

first=true
while IFS=, read -r pid mem gpu_uuid; do
    # Trim whitespace
    pid=$(echo "$pid" | xargs)
    mem=$(echo "$mem" | xargs)
    gpu_uuid=$(echo "$gpu_uuid" | xargs)

    # Get GPU ID from UUID
    gpu_id=$(nvidia-smi --query-gpu=index,gpu_uuid --format=csv,noheader | grep "$gpu_uuid" | cut -d',' -f1 | xargs)

    # Locate the K8s cgroup definition
    cgroup=$(cat /proc/$pid/cgroup 2>/dev/null | grep "kubepods" | head -n 1)

    namespace="unknown"
    pod_name="unknown"

    if [ ! -z "$cgroup" ]; then
        # Extract Pod UID and swap systemd underscores back to standard dashes
        pod_uid=$(echo "$cgroup" | grep -o 'pod[a-f0-9_\-]*' | sed 's/pod//' | tr '_' '-')

        if [ ! -z "$pod_uid" ]; then
            # Match UID against the K8s API
            pod_info=$(kubectl get pods -A -o jsonpath="{range .items[?(@.metadata.uid=='$pod_uid')]}{.metadata.namespace}{'|'}{.metadata.name}{end}" 2>/dev/null)
            if [ ! -z "$pod_info" ]; then
                namespace=$(echo "$pod_info" | cut -d'|' -f1)
                pod_name=$(echo "$pod_info" | cut -d'|' -f2)
            fi
        fi
    fi

    # Build JSON object
    if [ "$first" = true ]; then
        first=false
    else
        echo "," >> "$OUTPUT_FILE"
    fi

    cat >> "$OUTPUT_FILE" <<EOF
  {
    "pid": "$pid",
    "namespace": "$namespace",
    "pod": "$pod_name",
    "gpu_id": "$gpu_id",
    "gpu_memory_mb": "$mem",
    "node": "$NODE_NAME"
  }
EOF

done <<< "$nvidia_output"

echo "" >> "$OUTPUT_FILE"
echo "]" >> "$OUTPUT_FILE"
