ARG BASE_IMAGE=python:3.9-slim
FROM $BASE_IMAGE
ENV PBR_VERSION=6.0.0
COPY . /app/
WORKDIR /app/
ENV CONFIG ${CONFIG:-/app/conf.py}
RUN python3 -m pip install . -r requirements.txt
CMD fake-ipa --config "${CONFIG}"
