# Metal3 Utility Images - AI Agent Instructions

Instructions for AI coding agents. For details, see [README.md](README.md).

## Overview

Collection of utility container images for Metal3: iPXE builder, FakeIPA
for scalability testing, and keepalived for HA deployments.

## Repository Structure

| Directory | Purpose |
|-----------|---------|
| `fake-ipa/` | Simulates IPA for Ironic scalability testing |
| `ipxe-builder/` | Builds custom iPXE firmware with TLS/IPv6 support |
| `keepalived/` | Provides fixed IP for Ironic (HA/pivoting) |
| `hack/` | CI scripts (shellcheck, markdownlint) |

## Testing Standards

Run locally before PRs:

| Command | Purpose |
|---------|---------|
| `./hack/shellcheck.sh` | Shell script linting |
| `./hack/markdownlint.sh` | Markdown linting |

Build images with: `podman build -t <name> <directory>/`

## Code Conventions

- **Shell**: Use `set -eux` in scripts
- **Dockerfile**: Minimize layers, use multi-stage when appropriate

## Key Workflows

### Modifying an Image

1. Edit files in the image directory
1. Run `./hack/shellcheck.sh` for shell scripts
1. Build and test locally with `podman build`
1. Document environment variables in README.md

### Adding New Utility

1. Create directory with `Dockerfile` and scripts
1. Add documentation to main README.md
1. Ensure CI builds the image

## Code Review Guidelines

When reviewing pull requests:

1. **Image size** - Keep images minimal and focused
1. **Security** - No hardcoded credentials
1. **Documentation** - Document all environment variables
1. **Compatibility** - Test with both podman and docker

Focus on: `*/Dockerfile`, `*/scripts/`, `*/*.sh`.

## AI Agent Guidelines

1. Run `./hack/shellcheck.sh` before committing
1. Document new environment variables
1. Keep utilities focused and minimal

## Integration

- **keepalived**: Used by IrSO for Ironic HA
- **fake-ipa**: Used for Ironic scalability testing
- **ipxe-builder**: Builds firmware for PXE boot with TLS

## Related Documentation

- [Ironic Standalone Operator](https://github.com/metal3-io/ironic-standalone-operator)
- [Ironic Image](https://github.com/metal3-io/ironic-image)
