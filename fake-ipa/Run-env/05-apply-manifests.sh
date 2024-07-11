set -e
# Apply ironic
# Clone bmo
if [ ! -d "baremetal-operator/" ] ; then
    git clone "https://github.com/metal3-io/baremetal-operator.git"
fi

cd baremetal-operator/

# Ironic config file
cat <<'EOF' >ironic-deployment/overlays/e2e/ironic_bmo_configmap.env
HTTP_PORT=6180
PROVISIONING_IP=172.22.0.2
DEPLOY_KERNEL_URL=http://172.22.0.2:6180/images/ironic-python-agent.kernel
DEPLOY_RAMDISK_URL=http://172.22.0.2:6180/images/ironic-python-agent.initramfs
IRONIC_ENDPOINT=https://172.22.0.2:6385/v1/
CACHEURL=http://172.22.0.2/images
IRONIC_FAST_TRACK=true
IRONIC_KERNEL_PARAMS=console=ttyS0
IRONIC_INSPECTOR_VLAN_INTERFACES=all
PROVISIONING_CIDR=172.22.0.1/24
PROVISIONING_INTERFACE=ironicendpoint
DHCP_RANGE=172.22.0.10,172.22.0.100
IRONIC_INSPECTOR_ENDPOINT=http://172.22.0.2:5050/v1/
RESTART_CONTAINER_CERTIFICATE_UPDATED="false"
IRONIC_RAMDISK_SSH_KEY=ssh-rsa
IRONIC_USE_MARIADB=false
USE_IRONIC_INSPECTOR=false
OS_AGENT__REQUIRE_TLS=false
EOF

# Apply default ironic manifest without tls or authentication for simplicity
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/download/v1.15.1/cert-manager.yaml
kubectl -n cert-manager wait --for=condition=available deployment --all  --timeout=300s

echo "IRONIC_HTPASSWD=$(htpasswd -n -b -B admin password)" > ironic-deployment/overlays/e2e/ironic-htpasswd
echo "IRONIC_HTPASSWD=$(htpasswd -n -b -B admin password)" > ironic-deployment/overlays/e2e/ironic-inspector-htpasswd

cat <<'EOF' >ironic-deployment/overlays/e2e/ironic-auth-config
[ironic]
auth_type=http_basic
username=admin
password=password
EOF

kubectl apply -k config/namespace/
kubectl apply -k ironic-deployment/overlays/e2e
cd ..

kubectl -n baremetal-operator-system wait --for=condition=available deployment/ironic --timeout=300s

sudo pip install python-ironicclient


kubectl -n legacy get secret -n baremetal-operator-system   ironic-cert -o json -o=jsonpath="{.data.ca\.crt}" | base64 -d > "${HOME}/.config/openstack/ironic-ca.crt"

sudo "${HOME}/.config/openstack/ironic-ca.crt" tmp/cert/

# Create ironic node
sudo touch /opt/metal3-dev-env/ironic/html/images/image.qcow2

baremetal node create --driver redfish --driver-info \
  redfish_address=http://192.168.111.1:8000 --driver-info \
  redfish_system_id=/redfish/v1/Systems/27946b59-9e44-4fa7-8e91-f3527a1ef094 --driver-info \
  redfish_username=admin --driver-info redfish_password=password \
  --name default-node-1

baremetal node set default-node-1    --driver-info deploy_kernel="http://172.22.0.2:6180/images/ironic-python-agent.kernel"     --driver-info deploy_ramdisk="http://172.22.0.2:6180/images/ironic-python-agent.initramfs"
baremetal node set default-node-1       --instance-info image_source=http://172.22.0.1/images/image.qcow2     --instance-info image_checksum=http://172.22.0.1/images/image.qcow2

baremetal node create --driver redfish --driver-info \
redfish_address=http://192.168.111.1:8000 --driver-info \
redfish_system_id=/redfish/v1/Systems/27946b59-9e44-4fa7-8e91-f3527a1ef095 --driver-info \
redfish_username=admin --driver-info redfish_password=password \
--name default-node-2

baremetal node set default-node-2    --driver-info deploy_kernel="http://172.22.0.2:6180/images/ironic-python-agent.kernel"     --driver-info deploy_ramdisk="http://172.22.0.2:6180/images/ironic-python-agent.initramfs"
baremetal node set default-node-2       --instance-info image_source=http://172.22.0.1/images/image.qcow2     --instance-info image_checksum=http://172.22.0.1/images/image.qcow2