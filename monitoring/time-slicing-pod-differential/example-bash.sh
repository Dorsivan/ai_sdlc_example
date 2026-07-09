#!/bin/bash
echo -e "PID\t\tNAMESPACE\t\tPOD NAME"
echo -e "------------------------------------------------------------"

# Grab all currently active GPU PIDs
pids=$(nvidia-smi --query-compute-apps=pid --format=csv,noheader)

for pid in $pids; do
    # Locate the K8s cgroup definition
    cgroup=$(cat /proc/$pid/cgroup 2>/dev/null | grep "kubepods" | head -n 1)
    
    if [ -z "$cgroup" ]; then
        echo -e "$pid\t\t[Host System / Non-K8s Process]"
        continue
    fi
    
    # Extract Pod UID and swap systemd underscores back to standard dashes
    pod_uid=$(echo "$cgroup" | grep -o 'pod[a-f0-9_\-]*' | sed 's/pod//' | tr '_' '-')
    
    if [ ! -z "$pod_uid" ]; then
        # Match UID natively against the K8s API
        pod_info=$(kubectl get pods -A -o jsonpath="{range .items[?(@.metadata.uid=='$pod_uid')]}{.metadata.namespace}{'\t\t'}{.metadata.name}{'\n'}{end}" 2>/dev/null)
        if [ ! -z "$pod_info" ]; then
            echo -e "$pid\t\t$pod_info"
        else
            echo -e "$pid\t\tUnknown Pod (UID: $pod_uid)"
        fi
    else
        echo -e "$pid\t\tFailed to parse cgroup string"
    fi
done
