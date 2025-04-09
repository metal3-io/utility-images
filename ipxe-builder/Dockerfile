FROM quay.io/centos/centos:stream9

# image.version is set during image build by automation
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 iPXE Builder container image"
LABEL org.opencontainers.image.documentation="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 iPXE Builder"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.vendor="Metal3-io"

RUN dnf install -y gcc git-core make perl xz-devel python3-setuptools python3-jinja2

COPY buildipxe.sh embed.ipxe.j2 /bin/

CMD /bin/buildipxe.sh
