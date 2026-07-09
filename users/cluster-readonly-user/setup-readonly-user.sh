#!/usr/bin/env bash
#
# Creates a human-loginable, read-only ("view everything, change nothing") user
# on an OpenShift cluster.
#
# It will:
#   1. Generate/append an htpasswd entry (bcrypt-hashed password)
#   2. Create or update the 'htpass-secret' Secret in openshift-config
#   3. Add an htpasswd identity provider to OAuth/cluster (preserving existing ones)
#   4. Bind the user to the built-in 'cluster-reader' ClusterRole (read-only, cluster-wide)
#
# Prereqs: oc (logged in as cluster-admin), htpasswd, jq.
#
# Usage:
#   ./setup-readonly-user.sh -u <username> [-p <password>]
#   ./setup-readonly-user.sh -u viewer            # prompts for password
#   VIEWER_PASSWORD=secret ./setup-readonly-user.sh -u viewer
#
set -euo pipefail

# ---- config -----------------------------------------------------------------
SECRET_NAME="htpass-secret"
SECRET_NS="openshift-config"
PROVIDER_NAME="htpasswd_provider"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BINDING_TEMPLATE="${SCRIPT_DIR}/cluster-reader-binding.yaml"

USERNAME=""
PASSWORD="${VIEWER_PASSWORD:-}"

# ---- args -------------------------------------------------------------------
usage() { grep '^#' "$0" | sed 's/^# \{0,1\}//' | sed '/^!/d'; exit 1; }

while getopts ":u:p:h" opt; do
  case "$opt" in
    u) USERNAME="$OPTARG" ;;
    p) PASSWORD="$OPTARG" ;;
    h) usage ;;
    *) echo "Unknown option: -$OPTARG" >&2; usage ;;
  esac
done

# ---- preflight --------------------------------------------------------------
for bin in oc htpasswd jq; do
  command -v "$bin" >/dev/null 2>&1 || { echo "ERROR: '$bin' is required but not found in PATH." >&2; exit 1; }
done

if [[ -z "$USERNAME" ]]; then
  echo "ERROR: username is required (-u <username>)." >&2
  usage
fi

# Must be logged in.
if ! oc whoami >/dev/null 2>&1; then
  echo "ERROR: not logged in. Run 'oc login' as a cluster-admin first." >&2
  exit 1
fi
echo ">> Logged in as: $(oc whoami) @ $(oc whoami --show-server)"

# Need permission to edit OAuth + create ClusterRoleBindings.
if ! oc auth can-i update oauth.config.openshift.io/cluster >/dev/null 2>&1; then
  echo "WARNING: current user may lack permission to modify OAuth/cluster (need cluster-admin)." >&2
fi

if [[ -z "$PASSWORD" ]]; then
  read -r -s -p "Enter password for '$USERNAME': " PASSWORD; echo
  read -r -s -p "Confirm password: " PASSWORD2; echo
  [[ "$PASSWORD" == "$PASSWORD2" ]] || { echo "ERROR: passwords do not match." >&2; exit 1; }
fi
[[ -n "$PASSWORD" ]] || { echo "ERROR: password must not be empty." >&2; exit 1; }

WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT
HTPASSWD_FILE="${WORKDIR}/users.htpasswd"

# ---- 1. build the htpasswd file ---------------------------------------------
# Start from the existing secret (if any) so we don't clobber other users.
if oc get secret "$SECRET_NAME" -n "$SECRET_NS" >/dev/null 2>&1; then
  echo ">> Existing '$SECRET_NAME' found; appending user to it."
  oc get secret "$SECRET_NAME" -n "$SECRET_NS" \
    -o jsonpath='{.data.htpasswd}' | base64 -d > "$HTPASSWD_FILE" 2>/dev/null || true
fi

if [[ -s "$HTPASSWD_FILE" ]]; then
  # -b: batch (password on cmdline), -B: bcrypt. Updates entry if user exists.
  htpasswd -bB "$HTPASSWD_FILE" "$USERNAME" "$PASSWORD" >/dev/null
else
  # -c: create new file.
  htpasswd -cbB "$HTPASSWD_FILE" "$USERNAME" "$PASSWORD" >/dev/null
fi
echo ">> htpasswd entry generated for '$USERNAME' (bcrypt)."

# ---- 2. create/update the secret --------------------------------------------
# 'apply' via dry-run makes this idempotent (create or update).
oc create secret generic "$SECRET_NAME" \
  --from-file=htpasswd="$HTPASSWD_FILE" \
  -n "$SECRET_NS" \
  --dry-run=client -o yaml | oc apply -f -
echo ">> Secret '$SECRET_NS/$SECRET_NAME' applied."

# ---- 3. wire up the identity provider in OAuth/cluster -----------------------
PROVIDER_JSON=$(jq -n --arg name "$PROVIDER_NAME" --arg secret "$SECRET_NAME" '{
  name: $name,
  mappingMethod: "claim",
  type: "HTPasswd",
  htpasswd: { fileData: { name: $secret } }
}')

CURRENT=$(oc get oauth cluster -o json)

if echo "$CURRENT" | jq -e --arg n "$PROVIDER_NAME" \
     '(.spec.identityProviders // []) | any(.name == $n)' >/dev/null; then
  echo ">> OAuth provider '$PROVIDER_NAME' already present; leaving OAuth config unchanged."
else
  echo ">> Adding '$PROVIDER_NAME' to OAuth/cluster (preserving existing providers)."
  PATCHED=$(echo "$CURRENT" | jq --argjson p "$PROVIDER_JSON" \
    '.spec.identityProviders = ((.spec.identityProviders // []) + [$p])')
  echo "$PATCHED" | oc apply -f -
fi

# ---- 4. grant read-only cluster-wide access ---------------------------------
sed "s/VIEWER_USERNAME/${USERNAME}/g" "$BINDING_TEMPLATE" | oc apply -f -
echo ">> ClusterRoleBinding to 'cluster-reader' applied for '$USERNAME'."

# ---- done -------------------------------------------------------------------
SERVER="$(oc whoami --show-server)"
cat <<EOF

============================================================
  Read-only user '${USERNAME}' is set up.

  The OAuth operator may take ~1 minute to roll out the new
  login provider. Then log in with:

      oc login ${SERVER} -u ${USERNAME} -p '<password>'

  Verify it is truly read-only (after logging in as the user):
      oc auth can-i --list                 # should be get/list/watch only
      oc auth can-i create pods -A         # -> no
      oc get nodes                         # -> works (read)

  To remove everything later:
      oc delete clusterrolebinding ${USERNAME}-cluster-reader
      # then remove the user's line from the htpass-secret and/or
      # delete the htpasswd identity provider from OAuth/cluster.
============================================================
EOF
