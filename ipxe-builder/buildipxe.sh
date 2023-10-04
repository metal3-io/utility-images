#!/usr/bin/bash

set -euxo pipefail
# ENV VARIABLE CONFIG #

# This script should be used as an init container's entry point thus
# it is expected that the user would like to build the ipxe when this script
# is started. By default the script will try to build from cache and fails
# if the cache is unavailable.
export IPXE_CUSTOM_FIRMWARE_DIR="${IPXE_CUSTOM_FIRMWARE_DIR:-/shared/custom_ipxe_firmware}"
export IPXE_BUILD_FROM_CACHE="${IPXE_BUILD_FROM_CACHE:-true}"
export IPXE_BUILD_FROM_REPO="${IPXE_BUILD_FROM_REPO:-false}"
export IPXE_SHARED_FIRMWARE_SOURCE="${IPXE_SHARED_FIRMWARE_SOURCE:-/shared/ipxe-source}"
export IPXE_EMBED_SCRIPT="${IPXE_EMBED_SCRIPT:-/bin/embed.ipxe}"
export IPXE_EMBED_SCRIPT_TEMPLATE="${IPXE_EMBED_SCRIPT_TEMPLATE:-/bin/embed.ipxe.j2}"
export IPXE_RELEASE_BRANCH="${IPXE_RELEASE_BRANCH:-v1.21.1}"
export IPXE_ENABLE_IPV6="${IPXE_ENABLE_IPV6:-false}"
export IPXE_ENABLE_HTTPS="${IPXE_ENABLE_TLS:-false}"
export IPXE_CERT_FILE="${IPXE_CERT_FILE:-/certs/ipxe/tls.crt}"
export IPXE_KEY_FILE="${IPXE_KEY_FILE:-/certs/ipxe/tls.key}"
export IPXE_TLS_PORT="${IPXE_TLS_PORT:-8084}"
export IPXE_CHAIN_HOST="${IPXE_CHAIN_HOST:-0.0.0.0}"
# IPXE_BUILD_OPTIONS are not configurable directly
export IPXE_BUILD_OPTIONS="NO_WERROR=1 EMBED=${IPXE_EMBED_SCRIPT}"
# PREPARE SOURCE #

render_j2_config(){
    python3 -c 'import os; import sys; import jinja2; sys.stdout.write(jinja2.Template(sys.stdin.read()).render(env=os.environ))' < "$1" > "$2"
}

# Create debug folder
mkdir -p "/shared/ipxe-debug"

# In case building ipxe firmware from shared volume
if [[ "${IPXE_BUILD_FROM_CACHE}" == "true" ]]; then
    if [[ -r "${IPXE_SHARED_FIRMWARE_SOURCE}" ]]; then
        cp -r "${IPXE_SHARED_FIRMWARE_SOURCE}" "/tmp"
        ls -all "/tmp/ipxe-source"
    else
        echo "ERROR: can't build ipxe from cache, there is no path!" >&2
        exit 1
    fi
# In case building ipxe firmware from upstream git repo directly
# Requires Internet access!
elif [[ "${IPXE_BUILD_FROM_CACHE}" != "true" ]] \
         && [[ "${IPXE_BUILD_FROM_REPO}" == "true" ]]; then
    git clone --depth 1 --branch "${IPXE_RELEASE_BRANCH}" \
        "https://github.com/ipxe/ipxe.git" \
        "/tmp/ipxe-source"
# In case neither cache nor git repo based ipxe building is initiated,
# the script will fail with an error message!
elif [[ "${IPXE_BUILD_FROM_CACHE}" != "true" ]] \
        && [[ "${IPXE_BUILD_FROM_REPO}" != "true" ]]; then
        echo "ERROR: neither IPXE_BUILD_FROM_REPO nor IPXE_BUILD_FROM_CACHE has the value: true!" >&2
        echo "ERROR: the ipxe build script has got no source specified, it will exit with an error!" >&2
        exit 1
fi

# Copying the source to the work directory has failed.
if [[ ! -r "/tmp/ipxe-source" ]]; then
    echo "ERROR: the ipxe firmware source is missing from /tmp/ipxe-source!" >&2
    echo "ERROR: copying the source to the work directory has failed." >&2
    echo "ERROR: check the value of the IPXE_SHARED_FIRMWARE_SOURCE env variable!" >&2
    exit 1
fi

# BUILD #
ARCH=$(uname -m | sed 's/aarch/arm/')
# NOTE(elfosardo): warning should not be treated as errors by default
cd "/tmp/ipxe-source/src"
if [[ "${IPXE_ENABLE_IPV6}" == "true" ]]; then
    sed -i 's/^\/\/#define[ \t]NET_PROTO_IPV6/#define\tNET_PROTO_IPV6/g' \
        "config/general.h"
fi
if [[ "${IPXE_ENABLE_TLS}" == "true" ]]; then
    if [[ ! -r "${IPXE_CERT_FILE}" ]]; then
        echo "ERROR: iPXE TLS support is enabled but cert is missing!" >&2
        exit 1
    fi
    sed -i 's/^#define[ \t]DOWNLOAD_PROTO_HTTP/#undef\tDOWNLOAD_PROTO_HTTP/g' \
        "config/general.h"
    sed -i 's/^#undef[ \t]DOWNLOAD_PROTO_HTTPS/#define\tDOWNLOAD_PROTO_HTTPS/g' \
        "config/general.h"
    echo "IPXE BUILD OPTIONS ARE EXTENDED WITH CERTS!!!"
    render_j2_config "${IPXE_EMBED_SCRIPT_TEMPLATE}" "${IPXE_EMBED_SCRIPT}"
    export IPXE_BUILD_OPTIONS="${IPXE_BUILD_OPTIONS} CERT=${IPXE_CERT_FILE} TRUST=${IPXE_CERT_FILE}"
fi

sed -i 's/^\/\/#define[ \t]CONSOLE_SERIAL/#define\tCONSOLE_SERIAL/g' \
    "config/console.h"

# shellcheck disable=SC2086
/usr/bin/make "bin/undionly.kpxe" "bin-${ARCH}-efi/snponly.efi" ${IPXE_BUILD_OPTIONS}

mkdir -p "${IPXE_CUSTOM_FIRMWARE_DIR}"
# These files will be copied by the rundnsmasq script to the shared volume.
cp "/tmp/ipxe-source/src/bin/undionly.kpxe" \
   "/tmp/ipxe-source/src/bin-${ARCH}-efi/snponly.efi" \
   "${IPXE_CUSTOM_FIRMWARE_DIR}"

