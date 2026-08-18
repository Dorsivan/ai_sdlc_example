# OpenShift GitOps: Managing Cluster-Scoped Resources (PVs, Namespaces, etc.)

## The Problem

When trying to create a **PersistentVolume** (or any cluster-scoped resource) via an ArgoCD Application on OpenShift GitOps, you get:

```
Cluster level PersistentVolume cannot be managed in namespaces mode
```

This happens even if you've added PVs to the AppProject's `clusterResourceWhitelist`. The AppProject whitelist is necessary but **not sufficient** — the ArgoCD instance itself must be running in **cluster-scoped mode**.

## Why This Happens

OpenShift GitOps has **three layers** of permission for cluster-scoped resources:

1. **ArgoCD instance mode** (namespaced vs cluster-scoped) — controlled by the GitOps Operator via `ARGOCD_CLUSTER_CONFIG_NAMESPACES`. This is the gate that produces the error above.
2. **AppProject policy** (`clusterResourceWhitelist`) — ArgoCD's own policy layer that decides which resource types a project is allowed to manage.
3. **Kubernetes RBAC** — the actual ClusterRole/ClusterRoleBinding on the `argocd-application-controller` service account.

The error you're seeing is from **layer 1**. The operator blocks cluster-scoped resource management entirely for ArgoCD instances not listed in `ARGOCD_CLUSTER_CONFIG_NAMESPACES`, regardless of AppProject settings or RBAC.

### About the namespace list in the ArgoCD UI

When you look at your cluster in the ArgoCD UI, you'll see a list of namespaces. That list shows the namespaces the instance is allowed to deploy **namespaced resources** into (controlled by the `argocd.argoproj.io/managed-by` label). It does **not** control cluster-scoped resources — those are gated by the operator-level setting below.

## The Fix: Enable Cluster-Scoped Mode

### Step 1: Add your ArgoCD namespace to `ARGOCD_CLUSTER_CONFIG_NAMESPACES`

Edit the OpenShift GitOps Operator **Subscription**:

```bash
oc edit subscription openshift-gitops-operator -n openshift-gitops-operator
```

Add the `ARGOCD_CLUSTER_CONFIG_NAMESPACES` env var under `spec.config.env`:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: openshift-gitops-operator
  namespace: openshift-gitops-operator
spec:
  config:
    env:
      - name: ARGOCD_CLUSTER_CONFIG_NAMESPACES
        value: "openshift-gitops"
        # Comma-separated list if you have multiple ArgoCD instances:
        # value: "openshift-gitops, my-team-gitops"
```

> **⚠️ Security warning:** This grants the ArgoCD instance cluster-admin-level privileges. Only do this for instances managed by platform/cluster admins. Never grant this to instances accessible by non-admin users.

After saving, the operator will reconcile and create the necessary ClusterRole and ClusterRoleBinding for the ArgoCD application controller.

#### Verify it worked

```bash
# Check that the controller now has cluster-scoped permissions
oc auth can-i create persistentvolumes \
  --as system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller

# Expected output: yes
```

### Step 2: Whitelist PVs in your AppProject

Even with cluster-scoped mode enabled, the AppProject must explicitly allow PersistentVolumes:

```yaml
apiVersion: argoproj.io/v1alpha1
kind: AppProject
metadata:
  name: my-project
  namespace: openshift-gitops
spec:
  clusterResourceWhitelist:
    - group: ""
      kind: PersistentVolume
  # ... rest of your project spec
```

If you're using the `default` AppProject, it already allows all resources (`*/*`), so this step only applies to custom AppProjects.

### Step 3: Verify end-to-end

```bash
# 1. Confirm the ArgoCD instance is cluster-scoped
oc auth can-i create persistentvolumes \
  --as system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller
# Expected: yes

# 2. Confirm it can also manage other common cluster-scoped resources
oc auth can-i create namespaces \
  --as system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller
# Expected: yes

oc auth can-i create clusterroles \
  --as system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller
# Expected: yes

# 3. If using a user-defined ArgoCD instance (not in openshift-gitops namespace),
#    adjust the service account name accordingly:
oc auth can-i create persistentvolumes \
  --as system:serviceaccount:<your-namespace>:<your-argocd-name>-argocd-application-controller
```

## If You're Using a User-Defined ArgoCD Instance

If your ArgoCD instance is **not** the default one in `openshift-gitops` but a custom instance in another namespace (e.g., `my-team-gitops`):

1. Add that namespace to `ARGOCD_CLUSTER_CONFIG_NAMESPACES`:
   ```yaml
   - name: ARGOCD_CLUSTER_CONFIG_NAMESPACES
     value: "openshift-gitops, my-team-gitops"
   ```

2. The service account name follows the pattern `<argocd-instance-name>-argocd-application-controller`. Verify with:
   ```bash
   oc get sa -n my-team-gitops | grep application-controller
   ```

3. Test permissions:
   ```bash
   oc auth can-i create persistentvolumes \
     --as system:serviceaccount:my-team-gitops:<instance-name>-argocd-application-controller
   ```

## Common Cluster-Scoped Resources

These all require cluster-scoped mode to manage via ArgoCD:

| Resource | API Group | `oc auth can-i` test |
|---|---|---|
| PersistentVolume | `""` | `oc auth can-i create persistentvolumes --as system:serviceaccount:openshift-gitops:openshift-gitops-argocd-application-controller` |
| Namespace | `""` | `oc auth can-i create namespaces --as ...` |
| ClusterRole | `rbac.authorization.k8s.io` | `oc auth can-i create clusterroles --as ...` |
| ClusterRoleBinding | `rbac.authorization.k8s.io` | `oc auth can-i create clusterrolebindings --as ...` |
| StorageClass | `storage.k8s.io` | `oc auth can-i create storageclasses --as ...` |
| CustomResourceDefinition | `apiextensions.k8s.io` | `oc auth can-i create customresourcedefinitions --as ...` |

**PersistentVolumeClaim** is namespace-scoped and does **not** require cluster-scoped mode.

## Alternative: Use PVCs with Dynamic Provisioning

If you don't actually need to manage PVs directly, consider using **PersistentVolumeClaims** with a StorageClass that supports dynamic provisioning. PVCs are namespace-scoped resources and work fine in namespaced mode — no operator changes needed.

## References

- [OpenShift GitOps: Configuring cluster-scoped instances](https://docs.openshift.com/gitops/latest/declarative_clusterconfig/configuring-an-openshift-cluster-by-deploying-an-application-with-cluster-configurations.html)
- [OpenShift GitOps: Setting up an ArgoCD instance](https://docs.openshift.com/gitops/latest/argocd_instance/setting-up-argocd-instance.html)
- [ArgoCD AppProject Specification](https://argo-cd.readthedocs.io/en/stable/operator-manual/project-specification/)
