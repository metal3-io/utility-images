# Fake Ironic Python Agent

FakeIPA is a tool to help test ironic communication with IPA.

FakeIPA simulate the IPA by:

- Running an API server with the needed real IPA endpoint.
- Send back fake inspection data when requested.
- Lookup the node and save tokens.
- Heartbeating to Ironic API with several threads looping over
  a queue of fake agents.
- Faking the sync/async commands needed by ironic to inspect,
  clean and provision a node.

## Run FakeIPA

Dev-env provide an environment where we can test FakeIPA
Check WIP PR for more details:
<https://github.com/metal3-io/metal3-dev-env/pull/1450>
