#!/usr/bin/python3
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import logging

import requests

from fake_ipa import base

LOG = logging.getLogger(__name__)


class StandbyExtension(base.BaseAgentExtension):
    @base.async_command('power_off')
    def power_off(self):
        """Powers off the agent's system.

        As this is running with fakedriver we need to turn the node off
        by calling the redfish system.
        """
        LOG.info('Powering off system')
        sushytools_url = \
            '{}/redfish/v1/Systems/{}/Actions/ComputerSystem.Reset'.format(
                self.agent._config.get('FAKE_IPA_REDFISH_URL'),
                self.agent.system['uuid'])
        data = {
            "Action": "Reset",
            "ResetType": "ForceOff"
        }
        auth = requests.auth.HTTPBasicAuth(
            self.agent._config.get('FAKE_IPA_REDFISH_USER',
                                   'admin'),
            self.agent._config.get('FAKE_IPA_REDFISH_PASSWORD',
                                   'password'))
        requests.post(sushytools_url, json=data, verify=False, auth=auth,
                      headers={'Content-type': 'application/json'})

    @base.sync_command('get_partition_uuids')
    def get_partition_uuids(self):
        """Return partition UUIDs."""
        # NOTE(dtantsur): None means prepare_image hasn't been called (an empty
        # dict is used for whole disk images).
        return {}
