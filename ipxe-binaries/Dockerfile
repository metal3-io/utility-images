ARG BASE_IMAGE=quay.io/centos/centos:stream9-minimal
FROM $BASE_IMAGE AS ipxe-builder

## Build iPXE w/ IPv6 Support
## Note: we are pinning to a specific commit for reproducible builds.
## Updated as needed.
ARG IPXE_COMMIT_HASH=d0ea2b1bb8f78b219f74424d435b92ff8aa0ea8d
ARG TARGETARCH

WORKDIR /tmp

COPY prepare-ipxe.sh build-ipxe.sh /bin/

RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked prepare-ipxe.sh
RUN --mount=type=cache,target=/var/cache/dnf,sharing=locked build-ipxe.sh

FROM scratch

# image.version is set during image build by automation
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 iPXE binaries"
LABEL org.opencontainers.image.documentation="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 iPXE binaries"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.vendor="Metal3-io"

COPY --from=ipxe-builder /tmp/ipxe/out/ /ipxe/
