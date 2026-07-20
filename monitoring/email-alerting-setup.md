# Email Alerting Setup for OpenShift

## Overview
OpenShift uses Alertmanager for routing alerts. To send email notifications, you need to configure Alertmanager with SMTP settings.

## Configuration Steps

### 1. Create AlertmanagerConfig Resource

Create an `AlertmanagerConfig` in your namespace to define email receivers:

```yaml
apiVersion: monitoring.coreos.com/v1alpha1
kind: AlertmanagerConfig
metadata:
  name: gpu-alerts-email
  namespace: openshift-user-workload-monitoring
spec:
  route:
    groupBy: ['alertname', 'namespace']
    groupWait: 30s
    groupInterval: 5m
    repeatInterval: 12h
    receiver: 'gpu-team-email'
    matchers:
      - name: alertname
        value: GPUMemoryAvailableBelowZero
        matchType: =
  
  receivers:
    - name: 'gpu-team-email'
      emailConfigs:
        - to: 'your-team@example.com'
          from: 'openshift-alerts@example.com'
          smarthost: 'smtp.example.com:587'
          authUsername: 'smtp-user@example.com'
          authPassword:
            name: alertmanager-smtp-secret
            key: password
          headers:
            - key: Subject
              value: '[ALERT] GPU Memory Available Below Zero'
          text: |
            {{ range .Alerts }}
            Alert: {{ .Labels.alertname }}
            Namespace: {{ .Labels.namespace }}
            Pod: {{ .Labels.pod }}
            Description: {{ .Annotations.description }}
            Severity: {{ .Labels.severity }}
            {{ end }}
```

### 2. Create SMTP Secret

Store your SMTP password securely:

```bash
oc create secret generic alertmanager-smtp-secret \
  --from-literal=password='your-smtp-password' \
  -n openshift-user-workload-monitoring
```

### 3. Alternative: Configure Global Alertmanager

For cluster-wide email configuration, edit the Alertmanager config in the `openshift-monitoring` namespace:

```bash
oc -n openshift-monitoring create secret generic alertmanager-main \
  --from-literal=alertmanager.yaml="$(cat <<EOF
global:
  smtp_smarthost: 'smtp.example.com:587'
  smtp_from: 'openshift-alerts@example.com'
  smtp_auth_username: 'smtp-user@example.com'
  smtp_auth_password: 'your-smtp-password'
  smtp_require_tls: true

route:
  receiver: 'default'
  group_by: ['alertname', 'cluster', 'service']
  group_wait: 30s
  group_interval: 5m
  repeat_interval: 12h
  routes:
    - match:
        alertname: GPUMemoryAvailableBelowZero
      receiver: 'gpu-team'

receivers:
  - name: 'default'
    email_configs:
      - to: 'alerts@example.com'
  
  - name: 'gpu-team'
    email_configs:
      - to: 'gpu-team@example.com'
        headers:
          Subject: '[CRITICAL] GPU Memory Alert - {{ .GroupLabels.alertname }}'
EOF
)" --dry-run=client -o yaml | oc apply -f -
```

## Apply the Alert Rule

```bash
# Apply the PrometheusRule
oc apply -f gpu-memory-alert-rule.yaml

# Verify the rule is loaded
oc get prometheusrule -n openshift-user-workload-monitoring

# Check if alerts are firing
oc -n openshift-user-workload-monitoring get prometheusrule gpu-memory-alerts -o yaml
```

## Testing the Alert

You can verify the alert is working by checking Prometheus:

```bash
# Port forward to Prometheus
oc -n openshift-user-workload-monitoring port-forward svc/prometheus-user-workload 9090:9090

# Then visit http://localhost:9090/alerts in your browser
```

## Email Configuration Options

### Common SMTP Providers

**Gmail:**
- smarthost: `smtp.gmail.com:587`
- Requires app-specific password
- Enable "Less secure app access" or use OAuth2

**Office365:**
- smarthost: `smtp.office365.com:587`
- Use your Office365 credentials

**SendGrid:**
- smarthost: `smtp.sendgrid.net:587`
- authUsername: `apikey`
- authPassword: Your SendGrid API key

## Troubleshooting

1. Check Alertmanager logs:
```bash
oc -n openshift-user-workload-monitoring logs -l app.kubernetes.io/name=alertmanager
```

2. Verify the secret exists:
```bash
oc get secret alertmanager-smtp-secret -n openshift-user-workload-monitoring
```

3. Test email connectivity from a pod:
```bash
oc run -it --rm debug --image=alpine --restart=Never -- sh
apk add --no-cache curl
curl -v telnet://smtp.example.com:587
```

## Notes

- The alert fires after the condition is true for 2 minutes (`for: 2m`)
- Adjust `repeatInterval` to control how often repeat notifications are sent
- The `severity: warning` label can be changed to `critical` if needed
- Email templates support Go templating for customization
