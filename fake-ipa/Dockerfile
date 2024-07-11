ARG BASE_IMAGE=python:3.9-slim
FROM $BASE_IMAGE
ENV PBR_VERSION=6.0.0
COPY . /root/fake-ipa/
WORKDIR /root/fake-ipa/
ENV CONFIG ${CONFIG:-/root/fake-ipa/conf.py}
RUN python3 -m pip install -r requirements.txt
RUN python3 setup.py install
CMD fake-ipa --config $CONFIG