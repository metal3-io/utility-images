# Support FROM override
ARG BASE_IMAGE=ubuntu:22.04

FROM $BASE_IMAGE

# image.version is set during image build by automation
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 Keepalived container image"
LABEL org.opencontainers.image.documentation="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Keepalived"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.vendor="Metal3-io"

ARG DEBIAN_FRONTEND=noninteractive

RUN apt-get -y update && \
    apt-get -y install keepalived && \
    apt-get -y clean

COPY sample.keepalived.conf /etc/keepalived/keepalived.conf
COPY manage-keepalived.sh configure-nonroot.sh /bin/

RUN /bin/configure-nonroot.sh && rm /bin/configure-nonroot.sh

CMD ["/bin/bash", "/bin/manage-keepalived.sh"]
