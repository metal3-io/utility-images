#!/usr/bin/bash

set -eux

CUSTOM_CONF_DIR="${CUSTOM_CONF_DIR:-/conf}"
CUSTOM_DATA_DIR="${CUSTOM_DATA_DIR:-/data}"
KEEPALIVED_DEFAULT_CONF='/etc/keepalived/keepalived.conf'
KEEPALIVED_CONF_DIR="${CUSTOM_CONF_DIR}/keepalived"
KEEPALIVED_CONF="${KEEPALIVED_CONF_DIR}/keepalived.conf"
KEEPALIVED_DATA_DIR="${CUSTOM_DATA_DIR}/keepalived"

mkdir -p "${KEEPALIVED_CONF_DIR}" "${KEEPALIVED_DATA_DIR}"
cp "${KEEPALIVED_DEFAULT_CONF}" "${KEEPALIVED_CONF}"

# Format IP with appropriate prefix based on IP version
# Arguments: ip [prefix]
# If prefix is provided, use it; otherwise detect IPv4/IPv6 and use /32 or /128
format_ip_with_prefix() {
    local ip="$1"
    local prefix="${2:-}"

    if [[ -n "${prefix}" ]]; then
        echo "${ip}/${prefix}"
    elif [[ "${ip}" == *":"* ]]; then
        # IPv6
        echo "${ip}/128"
    else
        # IPv4
        echo "${ip}/32"
    fi
}

# Build the virtual_ipaddress block content and determine interface
# Supports two modes:
# 1. Legacy: PROVISIONING_IP and PROVISIONING_INTERFACE (single IP)
# 2. New: KEEPALIVED_VIRTUAL_IPS (multiple IPs, format: "ip,interface[,prefix] ...")
if [[ -n "${KEEPALIVED_VIRTUAL_IPS:-}" ]]; then
    # New format: space-separated entries, each entry is "ip,interface[,prefix]"
    first_interface=""
    virtual_ips=()

    for entry in ${KEEPALIVED_VIRTUAL_IPS}; do
        IFS=',' read -r ip interface prefix <<< "${entry}"

        if [[ -z "${first_interface}" ]]; then
            first_interface="${interface}"
        fi

        formatted_ip=$(format_ip_with_prefix "${ip}" "${prefix}")

        # Add "dev <interface>" to specify which interface this IP belongs to
        virtual_ips+=("${formatted_ip} dev ${interface}")
    done

    interface="${first_interface}"
    # Join array elements with newline and indentation for keepalived config
    assignedIP=$(printf '%s\n        ' "${virtual_ips[@]}" | head -c -9)
    # Escape newlines for sed replacement: replace newline with backslash-newline
    assignedIP="${assignedIP//$'\n'/\\
}"
else
    # Legacy format: single PROVISIONING_IP and PROVISIONING_INTERFACE
    interface="${PROVISIONING_INTERFACE}"
    assignedIP=$(format_ip_with_prefix "${PROVISIONING_IP}")
fi

sed -i "s~INTERFACE~${interface}~g" "${KEEPALIVED_CONF}"
sed -i "s~CHANGEIP~${assignedIP}~g" "${KEEPALIVED_CONF}"

exec /usr/sbin/keepalived --dont-fork --log-console \
    --pid="${KEEPALIVED_DATA_DIR}/keepalived.pid" \
    --vrrp_pid="${KEEPALIVED_DATA_DIR}/vrrp.pid" \
    --use-file="${KEEPALIVED_CONF}"
