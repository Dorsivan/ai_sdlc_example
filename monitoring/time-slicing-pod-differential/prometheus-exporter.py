#!/usr/bin/env python3

import json
import time
from prometheus_client import start_http_server, Gauge, CollectorRegistry
import os

# Create a custom registry
registry = CollectorRegistry()

# Define the metric
gpu_process_info = Gauge(
    'gpu_process_info',
    'GPU process information including pod, namespace, and GPU allocation',
    ['node', 'namespace', 'pod', 'gpu_id', 'pid'],
    registry=registry
)

def update_metrics():
    """Read the JSON file and update Prometheus metrics"""
    json_file = '/tmp/gpu_metrics.json'

    # Clear all previous metrics
    gpu_process_info.clear()

    try:
        if not os.path.exists(json_file):
            return

        with open(json_file, 'r') as f:
            data = json.load(f)

        for process in data:
            # Set metric with GPU memory usage as the value
            gpu_process_info.labels(
                node=process.get('node', 'unknown'),
                namespace=process.get('namespace', 'unknown'),
                pod=process.get('pod', 'unknown'),
                gpu_id=process.get('gpu_id', 'unknown'),
                pid=process.get('pid', 'unknown')
            ).set(float(process.get('gpu_memory_mb', 0)))

    except (json.JSONDecodeError, FileNotFoundError) as e:
        print(f"Error reading metrics file: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")

if __name__ == '__main__':
    # Start the HTTP server on port 8080
    start_http_server(8080, registry=registry)
    print("Prometheus exporter started on :8080")

    # Update metrics every 15 seconds
    while True:
        update_metrics()
        time.sleep(15)
