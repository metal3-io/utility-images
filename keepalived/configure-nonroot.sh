#!/usr/bin/bash

set -eux

# create nonroot image matching the keepalived manifest
NONROOT_USER="nonroot"
NONROOT_GROUP="nonroot"
NONROOT_UID=65532
NONROOT_GID=65532
CUSTOM_CONF_DIR=/conf
CUSTOM_DATA_DIR=/data

# run as non-root, allow editing the keepalived.conf during startup
groupadd -g "${NONROOT_GID}" "${NONROOT_GROUP}"
useradd -u "${NONROOT_UID}" -g "${NONROOT_GID}" -m "${NONROOT_USER}"

mkdir -p /run/keepalived
chown -R root:"${NONROOT_GROUP}" /etc/keepalived /run/keepalived
chmod 2775 /etc/keepalived /run/keepalived
chmod 664 /etc/keepalived/keepalived.conf

mkdir -p "${CUSTOM_CONF_DIR}" "${CUSTOM_DATA_DIR}"
chown "${NONROOT_USER}:${NONROOT_GROUP}" "${CUSTOM_CONF_DIR}" "${CUSTOM_DATA_DIR}"

setcap "cap_net_raw,cap_net_broadcast,cap_net_admin=+eip" /usr/sbin/keepalived
