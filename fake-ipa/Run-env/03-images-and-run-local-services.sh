# Set variables
SCRIPT_DIR="$(dirname "$(readlink -f "$0")")"
REGISTRY_NAME="registry"
REGISTRY_PORT="5000"
IMAGE_NAMES=(
    #    "quay.io/metal3-io/sushy-tools"
    "quay.io/metal3-io/ironic-client"
)

# Attach provisioning and baremetal network interfaces to minikube domain
virsh attach-interface --domain minikube --model virtio --source provisioning --type network --config
virsh attach-interface --domain minikube --model virtio --source baremetal --type network --config
podman pod create -n infra-pod || true
podman pod create -n ironic-pod || true
# Start podman registry if it's not already running
if ! podman ps | grep -q "$REGISTRY_NAME"; then
    podman run -d -p "$REGISTRY_PORT":"$REGISTRY_PORT" --name "$REGISTRY_NAME" docker.io/library/registry:2.7.1
fi

# Pull images, tag to local registry, and push to registry
for NAME in "${IMAGE_NAMES[@]}"; do
    # Pull and tag the image
    podman pull "$NAME"
    podman tag "$NAME" 127.0.0.1:"$REGISTRY_PORT"/localimages/"${NAME##*/}"
    # Push the image to the local registry
    podman push --tls-verify=false 127.0.0.1:5000/localimages/"${NAME##*/}"
done

./build-sushy-tools-and-fake-ipa-images.sh
# Set configuration options
cp ../conf.py "$SCRIPT_DIR/tmp/sushy-tools/conf.py"

# Create an htpasswd file
cat <<'EOF' >"$SCRIPT_DIR/tmp/sushy-tools/htpasswd"
admin:$2b$12$/dVOBNatORwKpF.ss99KB.vESjfyONOxyH.UgRwNyZi1Xs/W2pGVS
EOF
# Create directories
DIRECTORIES=(
    "/opt/metal3-dev-env/ironic/virtualbmc"
    "/opt/metal3-dev-env/ironic/virtualbmc/sushy-tools"
    "/opt/metal3-dev-env/ironic/html/images"
    "tmp/cert"
)
for DIR in "${DIRECTORIES[@]}"; do
    mkdir -p "$DIR"
    chmod -R 755 "$DIR"
done

# Run httpd container
podman run -d --net host --name httpd-infra \
    --pod infra-pod \
    -v /opt/metal3-dev-env/ironic:/shared \
    -e PROVISIONING_INTERFACE=provisioning \
    -e LISTEN_ALL_INTERFACES=false \
    --entrypoint /bin/runhttpd \
    quay.io/metal3-io/ironic:latest

# Generate ssh keys to use for virtual power and add them to authorized_keys
sudo ssh-keygen -f /root/.ssh/id_rsa_virt_power -P "" -q -y
sudo cat /root/.ssh/id_rsa_virt_power.pub | sudo tee -a /root/.ssh/authorized_keys

# Create and start a container for sushy-tools
podman run -d --net host --name sushy-tools --pod infra-pod \
    -v "$SCRIPT_DIR/tmp/sushy-tools:/root/sushy" \
    -v /root/.ssh:/root/ssh \
    127.0.0.1:5000/localimages/sushy-tools

# Create and start a container for fake-ipa
podman run -d --net host --name fake-ipa --pod infra-pod \
    -v "$SCRIPT_DIR/tmp/cert:/root/cert" \
    -v /root/.ssh:/root/ssh \
    127.0.0.1:5000/localimages/fake-ipa
