FROM golang:1.26 AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 go build -o /copilot-review .

FROM golang:1.26 AS gh-build
RUN CGO_ENABLED=0 go install github.com/cli/cli/v2/cmd/gh@6c470f60803784e1558b626022677c53dccb6016 # v2.92.0

FROM gcr.io/distroless/static-debian12

# image.version is set during image build by automation
LABEL org.opencontainers.image.authors="metal3-dev@googlegroups.com"
LABEL org.opencontainers.image.description="Metal3 Copilot Review Prow Plugin"
LABEL org.opencontainers.image.documentation="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.licenses="Apache License 2.0"
LABEL org.opencontainers.image.title="Metal3 Copilot Review Prow Plugin"
LABEL org.opencontainers.image.url="https://github.com/metal3-io/utility-images"
LABEL org.opencontainers.image.vendor="Metal3-io"

COPY --from=build /copilot-review /copilot-review
COPY --from=gh-build /go/bin/gh /usr/bin/gh

ENTRYPOINT ["/copilot-review"]
