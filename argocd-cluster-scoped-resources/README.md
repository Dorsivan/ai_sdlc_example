# ArgoCD: Cluster-Scoped Resources & Namespaced Mode

## The Problem

You're trying to create a **PersistentVolume (PV)** via an ArgoCD Application, and you've added PV permissions to the AppProject's `clusterResourceWhitelist` — but ArgoCD still fails with a permission error.

**Why?** Because ArgoCD was installed in **namespaced mode** (`namespace-install.yaml`), which only grants namespace-level RBAC to the ArgoCD service accounts. The AppProject `clusterResourceWhitelist` controls what ArgoCD *considers valid* for the project, but the underlying service account still needs actual Kubernetes RBAC to create those resources.

PersistentVolumes are **cluster-scoped** resources (they don't belong to any namespace), so namespace-level privileges can't touch them.

## Two Layers of Permission

ArgoCD has **two separate permission gates** for cluster-scoped resources:

1. **AppProject level** (`clusterResourceWhitelist`) — determines which cluster-scoped resource types an Application in that project is *allowed* to manage. This is ArgoCD's own policy layer.
2. **Kubernetes RBAC level** — the actual ClusterRole/ClusterRoleBinding attached to the `argocd-application-controller` service account. This is what Kubernetes enforces.

Both must allow the operation. The AppProject whitelist alone is not enough if the controller lacks Kubernetes-level permissions.

## Namespaced vs Cluster-Wide Installation

### Namespaced Mode (`namespace-install.yaml`)

- Uses **Roles** and **RoleBindings** (namespace-scoped)
- ArgoCD can only manage resources within its own namespace (for ArgoCD CRDs) and deploys to external clusters via credentials
- **Cannot create cluster-scoped resources** (PVs, ClusterRoles, Namespaces, etc.) on the local cluster without additional RBAC
- Ideal for: multi-tenant setups where ArgoCD deploys to external clusters

```bash
# Namespaced install (does NOT include CRDs)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/namespace-install.yaml

# CRDs must be installed separately
kubectl apply --server-side --force-conflicts -k "https://github.com/argoproj/argo-cd/manifests/crds?ref=stable"
```

### Cluster-Wide Mode (`install.yaml`)

- Uses **ClusterRoles** and **ClusterRoleBindings**
- ArgoCD has cluster-admin level access
- **Can create any resource type**, including PVs, Namespaces, ClusterRoles, etc.
- Ideal for: single-tenant or platform-team managed setups deploying to the same cluster

```bash
# Cluster-wide install (includes CRDs)
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

## How to Fix: Allow PV Creation in Namespaced Mode

If you want to **stay in namespaced mode** but allow PV creation, you need to grant the controller explicit Kubernetes RBAC. Don't switch to full cluster-wide install just for one resource type.

### Step 1: Create a ClusterRole for PVs

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: argocd-pv-manager
rules:
  - apiGroups: [""]
    resources: ["persistentvolumes"]
    verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]
```

### Step 2: Bind it to the ArgoCD Application Controller

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: argocd-pv-manager-binding
subjects:
  - kind: ServiceAccount
    name: argocd-application-controller
    namespace: argocd  # adjust if ArgoCD is in a different namespace
roleRef:
  kind: ClusterRole
  name: argocd-pv-manager
  apiGroup: rbac.authorization.k8s.io
```

### Step 3: Whitelist PVs in the AppProject

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
  namespace: argocd
spec:
  clusterResourceWhitelist:
    - group: ""
      kind: PersistentVolume
  # ... rest of your project spec
```

All three pieces are required:
- Kubernetes RBAC (ClusterRole + ClusterRoleBinding) → lets the controller actually create PVs
- AppProject whitelist → lets ArgoCD's policy engine allow it for this project

## Switching from Namespaced to Cluster-Wide

If you'd rather just switch to cluster-wide mode:

```bash
# Apply the cluster-wide manifests over the existing install
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

This will add the ClusterRole and ClusterRoleBinding resources that the namespaced install doesn't include. Existing ArgoCD resources (Applications, AppProjects, secrets) are preserved.

For HA environments, use `ha/install.yaml` or `ha/namespace-install.yaml` respectively.

## Quick Reference

| Resource | Scope | Needs ClusterRole? |
|---|---|---|
| PersistentVolume | Cluster | Yes |
| PersistentVolumeClaim | Namespace | No |
| Namespace | Cluster | Yes |
| ClusterRole | Cluster | Yes |
| ClusterRoleBinding | Cluster | Yes |
| StorageClass | Cluster | Yes |
| Deployment | Namespace | No |
| Service | Namespace | No |

## References

- [ArgoCD Installation Docs](https://argo-cd.readthedocs.io/en/stable/operator-manual/installation/)
- [AppProject Specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/project-specification/)
- [`install.yaml` (cluster-wide)](https://github.com/argoproj/argo-cd/blob/stable/manifests/install.yaml)
- [`namespace-install.yaml` (namespaced)](https://github.com/argoproj/argo-cd/blob/stable/manifests/namespace-install.yaml)
