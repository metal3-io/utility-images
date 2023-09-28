# Metal3 iPXE builder container

## Description

This repository provides the ability to build an OCI container that:
  - Provides customizable custom IPXE firmware building functionality.
  - Ability to either build IPXE firmware from an already existing cash.
  - Ability to pull IPXE firmware source code and build the firmware based
    on that.
  - Embed custom IPXE script in the firmware.
  - Enable IPV6 or TLS 1.3 support for the firmware.

## External runtime dependencies

- In order to build the iPXE firmware with TLS support, the user needs to
provide relevant certificate and certificate key files e.g. via a mounted
volume.

- If the ipxe-builder is instructed to build from existing iPXE source code
cache, then the cahce has to be provided e.g. via a mounted volume.

- In order to get a usable output the user needs to mount a directory
where the iPXE builder script can put the build outputs.

Expected paths to the external runtime dependencies can be configured
via run-time environment variables.

## Configuration

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
