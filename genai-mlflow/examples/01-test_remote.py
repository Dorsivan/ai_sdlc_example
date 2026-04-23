import mlflow

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

# Create a new experiment (if it doesn’t exist, this will create it)
experiment_name = "test_experiment1"
mlflow.set_experiment(experiment_name)

# Start a new MLflow run
with mlflow.start_run():
    mlflow.log_param("learning_rate", 0.01)
    mlflow.log_param("epochs", 10)
    mlflow.log_metric("accuracy", 0.95)

    print("Run logged successfully!")
