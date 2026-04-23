import mlflow
import os
import matplotlib.pyplot as plt
import numpy as np

# Set the tracking URI to your remote MLflow server

# This Route endpoint is accessible externally over **HTTPS**:
mlflow.set_tracking_uri("https://mlflow-route-<your-namespace>.apps.shift.nerc.mghpcc.org")  # Replace with your own remote server's route

# Alternatively: Set the tracking URI to a local MLflow server's service endpoint. This is accessible internally over **HTTP** on the specified port.

# This option is accessible within the cluster only, such as from:
# -   NERC RHOAI Workbench (Jupyter Notebooks)
# -   Another pod within your project namespace

# You can use either the service name or the fully qualified internal Hostname:

# Option 1: Using the service name
# mlflow.set_tracking_uri("http://mlflow-service:5000")

# Option 2: Using the full internal Hostname
# mlflow.set_tracking_uri("http://mlflow-service.<your-namespace>.svc.cluster.local:5000")

print(mlflow.get_tracking_uri())

# Set the S3/MinIO endpoint URL to your MinIO server API

# This Route endpoint is accessible externally over **HTTPS**:
os.environ["MLFLOW_S3_ENDPOINT_URL"] = "https://mlflow-minio-s3-<your-namespace>.apps.shift.nerc.mghpcc.org" # Replace with your own Minio API route

# Alternatively: Set the tracking URI to a local MiniIO instance's service endpoint. This is accessible internally over **HTTP** on the specified port.

# You can use either the service name or the fully qualified internal Hostname:

# Option 1: Using the service name
# mlflow.set_tracking_uri("http://mlflow-minio-service:9000")

# Option 2: Using the full internal Hostname
# mlflow.set_tracking_uri("http://mlflow-minio-service.<your-namespace>.svc.cluster.local:9000")

# Set S3/MinIO credentials (optional if already set as environment variables)
os.environ["AWS_ACCESS_KEY_ID"] = "xxx" # Replace with your own Access Key ID
os.environ["AWS_SECRET_ACCESS_KEY"] = "xxx" # Replace with your own Secret Access Key

# Create a new experiment (if it doesn’t exist, this will create it)
experiment_name = "test_experiment2"
mlflow.set_experiment(experiment_name)

# Start a new MLflow run
with mlflow.start_run():
    mlflow.log_param("learning_rate", 0.01)
    mlflow.log_param("epochs", 10)
    mlflow.log_metric("accuracy", 0.95)

    # Generate a sample plot and save it as a PNG
    x = np.linspace(0, 10, 100)
    y = np.sin(x)

    plt.figure()
    plt.plot(x, y)
    plt.title("Sample Sine Wave")
    plt.xlabel("X-axis")
    plt.ylabel("Y-axis")

    # Save the figure
    img_path = "sample_plot.png"
    plt.savefig(img_path)
    plt.close()

    # Log the PNG file as an artifact
    mlflow.log_artifact(img_path)

    # Cleanup
    os.remove(img_path)
    print(f"Artifact {img_path} logged successfully!")
