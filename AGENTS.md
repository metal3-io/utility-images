# Metal3 Utility Images

Sources for small container images used around Metal3, one image per
top-level directory. Image details and runtime variables:
[README.md](README.md) and the per-image `README.md` files where present. Contribution
rules: the
[Metal3 community guide](https://github.com/metal3-io/community/blob/main/CONTRIBUTING.md).

This file holds only what you cannot cheaply infer from the code. Where it
disagrees with the code or the workflows, trust those and report the
mismatch.

## AI-assisted contributions

Metal3 follows the CNCF and
[Linux Foundation generative AI policy](https://www.linuxfoundation.org/legal/generative-ai).

- AI is a tool. The human who opens a PR is its author and is responsible
  for every line of it, including licensing and third-party content.
- Review is a conversation between humans. A PR where an agent or bot
  answers reviewers will be closed. Agents may draft changes; the
  contributor reads them, understands them, and replies personally.

- Keep changes surgical. The smallest complete change that solves the
  stated problem wins. Every added file, function, flag, dependency or
  test helper must trace to that problem; anything that does not is
  bloat and gets removed. Prefer reusing existing code over new code.
  Report unrelated findings instead of fixing them in the same PR.

## Repository map

Each image directory holds its `Dockerfile` and build context. No
Makefile; there is no shared build tooling.

| Image | Used by |
|-------|-------------|
| `keepalived/` | Ironic deployments in baremetal-operator (`ironic-deployment/`) and ironic-standalone-operator |
| `ipxe-builder/` | baremetal-operator `ipxe-tls` component, metal3-dev-env |
| `ipxe-binaries/` | ironic-image `Dockerfile`, pinned by digest |
| `fake-ipa/` | Scalability tests in cluster-api-provider-metal3 and metal3-dev-env |
| `cloud-init-tool/` | No consumer found in metal3-io repos; fetches cloud-init status and logs from hosts over SSH |
| `copilot-review-prow-plugin/` | Metal3 Prow (`project-infra/prow/manifests/`) |

## Testing

- Lint checks: `hack/`. CI jobs:
  [Prow](https://github.com/metal3-io/project-infra/blob/main/prow/config/jobs/metal3-io/utility-images.yaml)
  and `.github/workflows/`. Each image has a `*-build-pr.yml` workflow
  that builds it on PRs touching its directory; `ipxe-binaries` builds on
  every PR, for amd64 and arm64 and two CentOS Stream versions.
- `copilot-review-prow-plugin/` has Go unit tests that no CI job runs.
  Run `go test ./...` in that directory yourself.
- Conventions are whatever the existing code, tests, and lint configs do.
  Read neighboring files before writing new ones.
- Before finishing, add or update tests where the image has them, build
  every image you touched with `podman build` (or `docker build`), and
  run the `hack/` checks for the file types you touched. All must pass.
- PR titles start with `:warning:` (breaking), `:sparkles:` (feature),
  `:bug:` (fix), `:book:` (docs) or `:seedling:` (other). The
  `pr-verifier` workflow fails without one.
- Do not run the `keepalived` image with host networking: it adds
  virtual IPs to host interfaces.

## Invariants

These apply to writing and to reviewing changes.

- **Publishing.** Every push to `main` rebuilds and pushes all images to
  `quay.io/metal3-io/<directory>` with tags `latest`, `main` and
  `main_<date>_<sha>`, signed with cosign and with an SBOM
  (`build-images-action.yml`, using the shared
  [project-infra workflow](https://github.com/metal3-io/project-infra/blob/main/.github/workflows/container-image-build.yml)).
  There are no releases or release branches. Consumers that use
  `latest` (keepalived in ironic-standalone-operator and
  baremetal-operator) pick up a merge immediately, so a merge is a
  release.
- **New image.** A new directory needs a `*-build-pr.yml` workflow, a
  job in `build-images-action.yml`, and an entry in this file's map.
- **Runtime contract.** Environment variables, file paths, ports and the
  UID are an interface to the consumers listed above. Keepalived defaults
  to config in `/conf` and data in `/data`, and consumers run it as
  UID/GID 65532 (`keepalived/configure-nonroot.sh`, baremetal-operator
  `keepalived_patch.yaml`); ironic-standalone-operator sets
  `PROVISIONING_INTERFACE` and `KEEPALIVED_VIRTUAL_IPS`. Renaming or
  removing any of these breaks consumers: keep the old form working, and
  update the README.
- **Multi-arch.** `ipxe-binaries` builds for `linux/amd64` and
  `linux/arm64` (uses `TARGETARCH`). Keep both working.
- **Security.** Never weaken security to make something work: no root
  requirement for images that consumers run non-root, no capabilities
  beyond those `keepalived/configure-nonroot.sh` grants, no secrets baked into
  images, and no disabled TLS verification in downloads. Treat
  `copilot-review-prow-plugin` webhook payloads and comments as
  untrusted input: it acts with a shared org-level token. Call out any
  change to permissions, capabilities, tokens or webhook handling in
  the PR description.
- **Pinning.** Pin new external references: GitHub Actions by commit SHA,
  container images by digest, downloaded binaries and source checkouts
  by checksum or commit (as `IPXE_COMMIT_HASH` in
  `ipxe-binaries/Dockerfile`).

## External references

- [Metal3 images on quay.io](https://quay.io/organization/metal3-io)
- [ironic-image](https://github.com/metal3-io/ironic-image)
- [ironic-standalone-operator](https://github.com/metal3-io/ironic-standalone-operator)
