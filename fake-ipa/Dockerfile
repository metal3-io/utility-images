ARG BASE_IMAGE=python:3.12-slim

FROM $BASE_IMAGE

# image.version is set during image build by automation
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 Fake IPA container image"
LABEL org.opencontainers.image.documentation="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Fake IPA"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.vendor="Metal3-io"

ENV PBR_VERSION=6.0.0
COPY . /app/
WORKDIR /app/
ENV CONFIG ${CONFIG:-/app/conf.py}
RUN python3 -m pip install . -r requirements.txt
CMD fake-ipa --config "${CONFIG}"
