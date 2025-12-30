# Metal3 utility images

This repository contains source code for the following container images.

## iPXE builder image

This directory provides the ability to build an OCI container that:

- Provides customizable custom IPXE firmware building functionality.

- Ability to either build IPXE firmware from an already existing cash.
- Ability to pull IPXE firmware source code and build the firmware based
  on that.
- Embed custom IPXE script in the firmware.
- Enable IPV6 or TLS 1.3 support for the firmware.

### External runtime dependencies

- In order to build the iPXE firmware with TLS support, the user needs to
  provide relevant certificate and certificate key files e.g. via a mounted
  volume.
- If the ipxe-builder is instructed to build from existing iPXE source code
  cache, then the cahce has to be provided e.g. via a mounted volume.
- In order to get a usable output the user needs to mount a directory
  where the iPXE builder script can put the build outputs.

Expected paths to the external runtime dependencies can be configured
via run-time environment variables.

### Configuration

The following environment variables can be passed in to customize run-time
functionality:

- BUILD_FROM_CACHE` - specifies whether the ipxebuilder should build
  the firmware from a local directory or not. (default `true`)
- `IPXE_BUILD_FROM_REPO` specifies whether the ipxebuilder should build
  from a remote git repo. (default `false`)
- `IPXE_SHARED_FIRMWARE_SOURCE` path to the iPXE source directory
  (default `/shared/ipxe-source`)
- `IPXE_EMBED_SCRIPT` path to the iPXE script that will be embedded in the
  custom iPXE firmware built by `the ipxebuilder`. (default `/bin/embed.ipxe`)
- `IPXE_EMBED_SCRIPT_TEMPLATE` path to the jinja template of the iPXE script
  that will be embedded in the custom firmware built by the ipxebuilder. This
  template is rendered in runtime by the builder script
  (default `/bin/embed.ipxe.j2`)
- `IPXE_RELEASE_BRANCH` the iPXE source code should be pulled from this branch
  , only relevant when `IPXE_BUILD_FROM_REPO` is `true` (default `v1.21.1`)
- `IPXE_ENABLE_IPV6` build the iPXE firmware with IPV6 support enabled `false`
- `IPXE_ENABLE_HTTPS` build the iPXE firmware with TLS support enabled `false`
- `IPXE_CUSTOM_FIRMWARE_DIR` output location for the build process
  (default: `/shared/custom_ipxe_firmware`)
- `IPXE_CERT_FILE` expected location of the TLS certificate used during build
  (default: `/certs/ipxe/tls.crt`)
- `IPXE_KEY_FILE` expected location of the TLS key used during build
  (default: `/certs/ipxe/tls.key`)
- `IPXE_TLS_PORT` this port will be used to start chainloading by a TLS enabled
  iPXE firmware, this value is used to render the embed.ipxe.j2 script template
  (default: `8084`)
- `IPXE_CHAIN_HOST` this ip will be used to start chainloading by a TLS enabled
  iPXE firmware, this value is used to render the embed.ipxe.j2 script template
  (default: `0.0.0.0`)

## Fake Ironic Python Agent

FakeIPA is a tool to help test ironic scalability.

FakeIPA simulate the IPA by:

- Running an API server with the needed real IPA endpoint.
- Send back fake inspection data when requested.
- Lookup the node and save tokens.
- Heartbeating to Ironic API with several threads looping over
  a queue of fake agents.
- Faking the sync/async commands needed by ironic to inspect,
  clean and provision a node.

## Keepalived

Keepalived container used in Ironic deployments. Keepalived is used to
provide fixed IP address for Ironic in such a manner that even after pivoting
operations the IP of Ironic stays persistent.

[Keepalived documentation](https://www.keepalived.org/manpage.html)

Deployment configuration options:

- `CUSTOM_CONF_DIR` - when specified, a subdirectory (named keepalived) will be
created under this path then the config files will be moved to the subdirectory
and the variable substitution will happen in this subdirectory
- `CUSTOM_DATA_DIR` - subdirectory (named keepalived) will be created here to
hold the keepalived and vrrp pid files
- `PROVISIONING_IP` - the fixed IP provided by keepalived (legacy mode, see
  below)
- `PROVISIONING_INTERFACE` - The name of the interface that will be used
  to "host" the fixed IP (legacy mode, see below)
- `KEEPALIVED_VIRTUAL_IPS` - Space-separated list of virtual IPs with their
  interfaces. Each entry has format: `ip,interface[,prefix]`. When set, this
  takes precedence over `PROVISIONING_IP` and `PROVISIONING_INTERFACE`.

### Configuration Modes

**Legacy mode** (single IP): Use `PROVISIONING_IP` and `PROVISIONING_INTERFACE`
for simple single-IP deployments. The script automatically detects IPv4 vs IPv6
and applies the correct prefix (`/32` for IPv4, `/128` for IPv6).

```bash
PROVISIONING_IP=192.168.0.100
PROVISIONING_INTERFACE=eth0
```

**Multi-IP mode**: Use `KEEPALIVED_VIRTUAL_IPS` for multiple IPs, different
interfaces, or mixed IPv4/IPv6 deployments. Format is space-separated entries
where each entry is `ip,interface[,prefix]`.

```bash
# Two IPs on different interfaces
KEEPALIVED_VIRTUAL_IPS="192.168.0.100,eth0 192.168.1.50,eth1"

# IPv6 with link-local address
KEEPALIVED_VIRTUAL_IPS="fe80::1,eth0,64 fd00::100,eth0,128"

# Mixed IPv4 and IPv6
KEEPALIVED_VIRTUAL_IPS="192.168.0.100,eth0 fd00::100,eth0"
```

NOTE: If run with container that has read-only root file-system, then
`CUSTOM_CONF_DIR`, `CUSTOM_DATA_DIR` and `/var/log` paths have to mounted from
external volume.
