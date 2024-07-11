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

import random
import time


from fake_ipa import base
from fake_ipa import error
from fake_ipa.heartbeater import Heatbeater
from fake_ipa import inspector
from fake_ipa.ironic_api_client import APIClient
from fake_ipa.ironic_api_client import get_ssl_client_options


class FakeIronicPythonAgent(base.ExecuteCommandMixin):
    """Class for faking ipa functionality."""

    agent_token = None

    @classmethod
    def initialize(cls, config, logger, api):
        config.setdefault('FAKE_IPA_INSPECTION_CALLBACK_URL',
                          'http://localhost:5050/v1/continue')
        config.setdefault('FAKE_IPA_MIN_BOOT_TIME', 180)
        config.setdefault('FAKE_IPA_MAX_BOOT_TIME', 240)
        cls._config = config
        cls._logger = logger
        cls.api = api
        Heatbeater.initialize(config, logger).run_heartbeater_threads(2)
        return cls

    def __init__(self, system, api_url,
                 ip_lookup_attempts=6, ip_lookup_sleep=10,
                 lookup_timeout=300, lookup_interval=1):
        super(FakeIronicPythonAgent, self).__init__()
        self.system = system
        self.api_url = api_url
        if self.api_url:
            self.api_client = APIClient.initialize(
                self._config, self._logger)(self.system, self.api_url)
            self.heartbeater = Heatbeater()
        self.lookup_timeout = lookup_timeout
        self.lookup_interval = lookup_interval
        self.ip_lookup_attempts = ip_lookup_attempts
        self.ip_lookup_sleep = ip_lookup_sleep

    def boot(self):

        # Waiting for ironic to unlock the node after changing the power state
        time.sleep(random.randint(
            self._config["FAKE_IPA_MIN_BOOT_TIME"],
            self._config["FAKE_IPA_MAX_BOOT_TIME"]))

        uuid = None
        verify, cert = get_ssl_client_options(self._config)
        if self._config["FAKE_IPA_INSPECTION_CALLBACK_URL"]:
            self._logger.debug(
                "Starting inspection node %s and sending data to %s",
                self.system["name"],
                self._config["FAKE_IPA_INSPECTION_CALLBACK_URL"])
            try:
                uuid = inspector.inspect(
                    self.system,
                    self._config["FAKE_IPA_INSPECTION_CALLBACK_URL"],
                    verify, cert,
                    self._logger)
            except Exception as exc:
                self._logger.error('Failed to perform inspection: %s', exc)
            self._logger.debug("Inspection UUID %s", uuid)

        if self.api_url:
            content = self.api_client.lookup_node(
                timeout=self.lookup_timeout,
                starting_interval=self.lookup_interval,
                node_uuid=uuid)
            self._logger.debug('Received lookup results: %s', content)
            self.process_lookup_data(content)

        elif self._config["FAKE_IPA_INSPECTION_CALLBACK_URL"]:
            self._logger.info(
                'No FAKE_IPA_API_URL configured,'
                'Heartbeat and lookup'
                'skipped for inspector.')
        else:
            self._logger.error(
                'Neither FAKE_IPA_API_URL nor'
                'FAKE_IPA_INSPECTION_CALLBACK_URL'
                'found, please check your'
                'pxe append parameters.')

        if self.api_url:
            # Add the new node to heartbeater queue
            self._logger.info(
                'Adding Node %s to the heartbeater queue', self.system['uuid'])
            Heatbeater.add_to_q(self.system, self)

    def process_lookup_data(self, content):
        """Update agent configuration from lookup data."""

        # This is a different data from what we init the node
        self.node = content['node']
        self._logger.info('Lookup succeeded, node UUID is %s',
                          self.node['uuid'])
        FakeIronicPythonAgent.api.agents[self.node['uuid']] = self
        self.heartbeat_timeout = content['config']['heartbeat_timeout']
        # Update config with values from Ironic
        config = content.get('config', {})
        if config.get('agent_token_required'):
            self.agent_token_required = True
        token = config.get('agent_token')
        if token:
            if len(token) >= 32:
                self._logger.debug('Agent token recorded as designated by '
                                   'the ironic installation.')
                self.agent_token = token
                # set with-in the API client.
                self.api_client.agent_token = token
            elif token == '******':
                self._logger.error('The agent token has already been '
                                   'retrieved. IPA may not operate as '
                                   'intended and the deployment may fail '
                                   'depending on settings in the ironic '
                                   'deployment.')
                if not self.agent_token and self.agent_token_required:
                    self._logger.error('Ironic is signaling that agent tokens '
                                       'are required, however we do not have '
                                       'a token on file. '
                                       'This is likely **FATAL**.')
            else:
                self._logger.info('An invalid token was received.')
        if self.agent_token:
            # Explicitly set the token in our API client before
            # starting heartbeat operations.
            self.api_client.agent_token = self.agent_token

    def force_heartbeat(self):
        self.heartbeater.force_heartbeat()

    def list_command_results(self):
        """Get a list of command results.

        :returns: list of :class:`fake_ipa.extensions.base.
                  BaseCommandResult` objects.
        """
        self.refresh_last_async_command()
        return list(self.command_results.values())

    def get_command_result(self, result_id):
        """Get a specific command result by ID.

        :returns: a :class:`fake_ipa.extensions.base.
                  BaseCommandResult` object.
        :raises: RequestedObjectNotFoundError if command with the given ID
                 is not found.
        """

        try:
            return self.command_results[result_id]
        except KeyError:
            raise error.RequestedObjectNotFoundError('Command Result',
                                                     result_id)

    def validate_agent_token(self, token):
        # We did not get a token, i.e. None and
        # we've previously seen a token, which is
        # a mid-cluster upgrade case with long-running ramdisks.
        if (not token and self.agent_token
                and not self.agent_token_required):
            return True
        return self.agent_token == token
