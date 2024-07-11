# Fake ironic python agent

Fake ipa is a tool to help test ironic communication with IPA.

Fake ipa simulate the IPA by:

- Running an API server with the needed real IPA endpoint.
- Send back fake inspection data when requested.
- lookup the node and save tokens.
- Heartbeating to ironic API with several threads looping over
  a queue of fake agents.
- Faking the sync/async commands needed by ironic to inspect,
  clean and provision a node.

## Run Fake ipa with ironic

### Requirements

Machine: `4c / 16gb / 100gb`
OS: `CentOS9-20220330`

### Test fake ipa

1. clone the env scripts `cd` inside `fake-ipa/Run-env` folder
2. check configs in `config.py`
3. run init `./Init-environment.sh`
4. to just rebuild fake-ipa from the local repo run `./rebuild-fipa.sh`

### Use ironic with fake-ipa

At this step there will be an ironic environment using fake-ipa,
by default there will be two nodes created on ironic you can list them with:
`baremetal node list`

To manage the a node using the ironicclient:
`baremetal node manage <node-name>`

To inspect use: `baremetal node inspect <node-name>`
then you can provide and deploy image on the node with:

```bash
baremetal node provide <node-name>
baremetal node deploy <node-name>
```

### Clean

To clean the env `./clean.sh`
