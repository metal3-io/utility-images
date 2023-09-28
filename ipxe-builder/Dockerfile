FROM quay.io/centos/centos:stream9

RUN dnf install -y gcc git-core make perl xz-devel python3-setuptools python3-jinja2

COPY buildipxe embed.ipxe.j2 /bin/

CMD /bin/buildipxe
