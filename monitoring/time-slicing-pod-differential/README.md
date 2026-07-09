# GPU Pod Allocation Monitoring

This monitoring solution tracks which Kubernetes pods are using which GPUs on which nodes in real-time.

## Components

1. **DaemonSet** - Runs on all GPU nodes to collect GPU process information
2. **Prometheus Exporter** - Exposes metrics in Prometheus format
3. **ServiceMonitor** - Configures Prometheus scraping
4. **Grafana Dashboard** - Visualizes GPU allocation

## Architecture

Each DaemonSet pod contains two containers:
- **gpu-collector**: Runs the bash script every 15 seconds to collect GPU process data
- **prometheus-exporter**: Python service exposing metrics at `:8080/metrics`

## Metrics Exposed

```
gpu_process_info{node="node1", namespace="default", pod="llm-pod-x", gpu_id="0", pid="12345"} 1024
```

- **Value**: GPU memory allocated (MB)
- **Labels**:
  - `node`: Kubernetes node name
  - `namespace`: Pod namespace
  - `pod`: Pod name
  - `gpu_id`: GPU device ID (0, 1, 2, etc.)
  - `pid`: Process ID

## Deployment Steps

### 1. Build and Push the Exporter Image

```bash
# Build the image
podman build -t quay.io/your-org/gpu-pod-exporter:latest .

# Push to your registry
podman push quay.io/your-org/gpu-pod-exporter:latest
```

### 2. Update the DaemonSet

Edit `daemonset.yaml` and replace:
```yaml
image: quay.io/your-org/gpu-pod-exporter:latest
```
with your actual image registry path.

### 3. Deploy to OpenShift

```bash
# Create the monitoring namespace if it doesn't exist
oc create namespace monitoring

# Apply the DaemonSet and RBAC
oc apply -f daemonset.yaml

# Apply the ServiceMonitor
oc apply -f servicemonitor.yaml
```

### 4. Import Grafana Dashboard

1. Log into Grafana
2. Go to **Dashboards** → **Import**
3. Upload `grafana-dashboard.json`
4. Select your Prometheus datasource
5. Click **Import**

## Dashboard Features

The dashboard includes:

1. **Current State Table**: Shows all active GPU processes with pod, namespace, node, GPU ID, and memory usage
2. **GPU Memory by Node and GPU**: Time-series graph showing memory usage per GPU
3. **GPU Memory by Namespace**: Time-series showing which namespaces are using GPUs
4. **Stats Panel**: 
   - Total active GPU processes
   - Nodes with active GPUs
   - Total GPU memory allocated
   - Active namespaces using GPUs

## Troubleshooting

### Check if pods are running

```bash
oc get pods -n monitoring -l app=gpu-pod-monitor
```

### View collector logs

```bash
oc logs -n monitoring -l app=gpu-pod-monitor -c gpu-collector
```

### View exporter logs

```bash
oc logs -n monitoring -l app=gpu-pod-monitor -c prometheus-exporter
```

### Test metrics endpoint

```bash
# Port-forward to a pod
oc port-forward -n monitoring <pod-name> 8080:8080

# Curl the metrics
curl http://localhost:8080/metrics
```

### Check ServiceMonitor

```bash
oc get servicemonitor -n monitoring gpu-pod-monitor -o yaml
```

## Requirements

- OpenShift/Kubernetes cluster with GPU nodes
- NVIDIA GPU Operator installed (provides `nvidia-smi`)
- Prometheus Operator (for ServiceMonitor support)
- Grafana

## Permissions

The DaemonSet requires:
- `hostPID: true` - To read process cgroups from `/proc`
- `privileged: true` - To access GPU information via `nvidia-smi`
- ClusterRole to list/get pods across all namespaces

## Customization

### Change scrape interval

Edit `servicemonitor.yaml`:
```yaml
interval: 30s  # Change to desired interval
```

### Change collection interval

Edit the `gpu-collector` container in `daemonset.yaml`:
```bash
sleep 15  # Change to desired interval in seconds
```

### Filter by namespace

To only show certain namespaces in Grafana, add a template variable or modify the queries to filter by namespace.
