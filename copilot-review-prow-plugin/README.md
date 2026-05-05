# Copilot Review Prow Plugin

A [Prow external plugin](https://docs.prow.k8s.io/docs/components/plugins/external-plugins/)
that lets GitHub org members request a
[GitHub Copilot code review](https://docs.github.com/en/copilot/using-github-copilot/code-review/using-copilot-code-review)
on a pull request by commenting `/copilot-review`.

It uses a shared org-level token so that users without their own Copilot
seat can still trigger a review.

## Usage

Comment on any pull request in a configured repository:

```text
/copilot-review
```

The plugin will verify that the commenter is a member of the GitHub org,
then add `@copilot` as a reviewer using the `gh` CLI.

## Environment Variables

| Variable               | Description                                                            |
| ---------------------- | ---------------------------------------------------------------------- |
| `COPILOT_REVIEW_TOKEN` | GitHub token used by `gh` CLI to request the review (highest priority) |
| `GH_TOKEN`             | Fallback GitHub token if `COPILOT_REVIEW_TOKEN` is not set             |
| `GITHUB_TOKEN`         | Fallback if neither of the above is set                                |

At least one of these must be set to a token with permission to add
reviewers to pull requests.

## Command-Line Flags

| Flag                 | Default             | Description                                        |
| -------------------- | ------------------- | -------------------------------------------------- |
| `--port`             | `8888`              | Port to listen on                                  |
| `--dry-run`          | `true`              | Dry run mode — uses API tokens but does not mutate |
| `--hmac-secret-file` | `/etc/webhook/hmac` | Path to the GitHub HMAC webhook secret             |

Standard Prow GitHub and instrumentation flags are also supported.

## Building the Image

```bash
docker build -t copilot-review-prow-plugin copilot-review-prow-plugin/
```

The Dockerfile compiles the Go binary and bundles the
[`gh` CLI](https://cli.github.com/) into a distroless image.
