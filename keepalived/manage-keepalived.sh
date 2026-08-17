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

vrid="${KEEPALIVED_VRID:-1}"
if [[ ! "${vrid}" =~ ^[0-9]+$ ]] || (( 10#${vrid} < 1 || 10#${vrid} > 255 )); then
    echo "ERROR: KEEPALIVED_VRID must be an integer in the range 1..255," \
         "got '${vrid}'" >&2
    exit 1
fi

# Tracing is disabled from here on so that the password never reaches the
# `set -x` output. VRRP truncates auth_pass to 8 bytes, only those are compared.
set +x
auth_pass=""
if [[ -n "${KEEPALIVED_AUTH_PASS:-}" && -n "${KEEPALIVED_AUTH_PASS_FILE:-}" ]]; then
    echo "ERROR: KEEPALIVED_AUTH_PASS and KEEPALIVED_AUTH_PASS_FILE are" \
         "mutually exclusive, set only one of them" >&2
    exit 1
elif [[ -n "${KEEPALIVED_AUTH_PASS:-}" ]]; then
    auth_pass="${KEEPALIVED_AUTH_PASS}"
elif [[ -n "${KEEPALIVED_AUTH_PASS_FILE:-}" ]]; then
    if [[ ! -r "${KEEPALIVED_AUTH_PASS_FILE}" ]]; then
        echo "ERROR: KEEPALIVED_AUTH_PASS_FILE" \
             "'${KEEPALIVED_AUTH_PASS_FILE}' does not exist or is not" \
             "readable" >&2
        exit 1
    fi
    auth_pass="$(cat -- "${KEEPALIVED_AUTH_PASS_FILE}")"
    auth_pass="${auth_pass#"${auth_pass%%[![:space:]]*}"}"
    auth_pass="${auth_pass%"${auth_pass##*[![:space:]]}"}"
    if [[ -z "${auth_pass}" ]]; then
        echo "ERROR: KEEPALIVED_AUTH_PASS_FILE" \
             "'${KEEPALIVED_AUTH_PASS_FILE}' is empty" >&2
        exit 1
    fi
fi

if [[ -n "${auth_pass}" ]]; then
    if [[ "${auth_pass}" == *[[:space:]]* ]] \
        || [[ "${auth_pass}" == *['"\~']* ]] \
        || [[ "${auth_pass}" =~ [^[:print:]] ]]; then
        echo "ERROR: the VRRP authentication password must not contain" \
             "whitespace, double quotes, backslashes, '~' or non-printable" \
             "characters" >&2
        exit 1
    fi
    if (( ${#auth_pass} > 8 )); then
        echo "WARNING: the VRRP authentication password is" \
             "${#auth_pass} characters long; VRRP truncates it to 8 bytes," \
             "only the first 8 are significant" >&2
    fi
    authentication="authentication {
        auth_type PASS
        auth_pass ${auth_pass//&/\\&}
    }"
    # Escape newlines for sed replacement: replace newline with backslash-newline
    auth_expr="s~AUTHENTICATION~${authentication//$'\n'/\\
}~"
else
    auth_expr='/AUTHENTICATION/d'
fi
unset auth_pass authentication KEEPALIVED_AUTH_PASS
set -x

sed -i "s~INTERFACE~${interface}~g" "${KEEPALIVED_CONF}"
sed -i "s~CHANGEIP~${assignedIP}~g" "${KEEPALIVED_CONF}"
sed -i "s~VRID~${vrid}~g" "${KEEPALIVED_CONF}"
set +x
sed -i "${auth_expr}" "${KEEPALIVED_CONF}"
unset auth_expr
set -x

exec /usr/sbin/keepalived --dont-fork --log-console \
    --pid="${KEEPALIVED_DATA_DIR}/keepalived.pid" \
    --vrrp_pid="${KEEPALIVED_DATA_DIR}/vrrp.pid" \
    --use-file="${KEEPALIVED_CONF}"
