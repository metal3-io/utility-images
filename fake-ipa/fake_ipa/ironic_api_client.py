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

import json

import requests
import tenacity

from fake_ipa import encoding
from fake_ipa import error

MIN_IRONIC_VERSION = (1, 31)
AGENT_VERSION_IRONIC_VERSION = (1, 36)
AGENT_TOKEN_IRONIC_VERSION = (1, 62)
AGENT_VERIFY_CA_IRONIC_VERSION = (1, 68)
MAX_KNOWN_VERSION = AGENT_VERIFY_CA_IRONIC_VERSION
# TODO(Mohammed) FIX to a correct version
# Add a parameter to set ipa version
__version__ = "1.22"


class APIClient():

    api_version = 'v1'
    lookup_api = '/%s/lookup' % api_version
    heartbeat_api = '/%s/heartbeat/{uuid}' % api_version
    _ironic_api_version = None
    agent_token = None

    @classmethod
    def initialize(cls, config, logger):
        cls._logger = logger
        cls._config = config
        return cls

    def __init__(self, node, api_url):
        self.api_url = api_url.rstrip('/')
        self.node = node

        # Only keep alive a maximum of 2 connections to the API. More will be
        # opened if they are needed, but they will be closed immediately after
        # use.
        adapter = requests.adapters.HTTPAdapter(pool_connections=2,
                                                pool_maxsize=2)
        self.session = requests.Session()
        self.session.mount(self.api_url, adapter)

        self.encoder = encoding.RESTJSONEncoder()

    def _request(self, method, path, data=None, headers={}, **kwargs):
        request_url = '{api_url}{path}'.format(api_url=self.api_url, path=path)

        if data is not None:
            data = self.encoder.encode(data)

        verify, cert = get_ssl_client_options(self._config)

        headers.update({
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        })

        return self.session.request(method,
                                    request_url,
                                    headers=headers,
                                    data=data,
                                    verify=verify,
                                    cert=cert,
                                    **kwargs)

    def _get_ironic_api_version_header(self, version=None):
        if version is None:
            ironic_version = self._get_ironic_api_version()
            version = min(ironic_version, AGENT_TOKEN_IRONIC_VERSION)
        return {'X-OpenStack-Ironic-API-Version': '%d.%d' % version}

    def _get_ironic_api_version(self):
        if self._ironic_api_version:
            return self._ironic_api_version
        try:
            response = self._request('GET', '/')
            data = json.loads(response.content)
            version = data['default_version']['version'].split('.')
            self._ironic_api_version = (int(version[0]), int(version[1]))
            return self._ironic_api_version
        except Exception:
            self._logger.exception("An error occurred while attempting to \
                                   discover the available Ironic API \
                                   versions, falling "
                                   "back to using version %s",
                                   ".".join(map(str, MIN_IRONIC_VERSION)))
            return MIN_IRONIC_VERSION

    def _error_from_response(self, response):
        try:
            body = response.json()
        except ValueError:
            text = response.text
        else:
            body = body.get('error_message', body)
            if not isinstance(body, dict):
                # Old ironic format
                try:
                    body = json.loads(body)
                except json.decoder.JSONDecodeError:
                    body = {}

            text = (body.get('faultstring')
                    or body.get('title')
                    or response.text)

        return 'Error %d: %s' % (response.status_code, text)

    def lookup_node(self, timeout, starting_interval,
                    node_uuid=None, max_interval=30):
        retry = tenacity.retry(
            retry=tenacity.retry_if_result(lambda r: r is False),
            stop=tenacity.stop_after_delay(timeout),
            wait=tenacity.wait_random_exponential(min=starting_interval,
                                                  max=max_interval),
            reraise=True)
        try:
            return retry(self._do_lookup)(node_uuid=node_uuid)
        except tenacity.RetryError:
            raise error.LookupNodeError('Could not look up node info. Check '
                                        'logs for details.')

    def _do_lookup(self, node_uuid):
        """The actual call to lookup a node."""
        params = {
            'addresses': self.node.get('nics')[0]['mac']
        }
        if node_uuid:
            params['node_uuid'] = node_uuid

        self._logger.debug(
            'Looking up node with addresses %r and UUID %s at %s',
            params['addresses'], node_uuid, self.api_url)

        try:
            response = self._request(
                'GET', self.lookup_api,
                headers=self._get_ironic_api_version_header(),
                params=params)
        except (requests.exceptions.Timeout,
                requests.exceptions.ConnectTimeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.ReadTimeout,
                requests.exceptions.HTTPError) as err:
            self._logger.warning(
                'Error detected while attempting to perform lookup '
                'with %s, retrying. Error: %s', self.api_url, err
            )
            return False
        except Exception as err:
            msg = ('Unhandled error looking up node with addresses {} at '
                   '{}: {}'.format(params['addresses'], self.api_url, err))
            self._logger.exception(msg)
            return False

        if response.status_code != requests.codes.OK:
            self._logger.warning(
                'Failed looking up node with addresses %r at %s. '
                '%s. Check if inspection has completed.',
                params['addresses'], self.api_url,
                self._error_from_response(response)
            )
            return False

        try:
            content = json.loads(response.content)
        except json.decoder.JSONDecodeError as e:
            self._logger.warning('Error decoding response: %s', e)
            return False

        # Check for valid response data
        if 'node' not in content or 'uuid' not in content['node']:
            self._logger.warning(
                'Got invalid node data in response to query for node '
                'with addresses %r from %s: %s',
                params['addresses'], self.api_url, content,
            )
            return False

        if 'config' not in content:
            # Old API
            try:
                content['config'] = {'heartbeat_timeout':
                                     content.pop('heartbeat_timeout')}
            except KeyError:
                self._logger.warning(
                    'Got invalid heartbeat from the API: %s', content)
                return False

        # Got valid content
        return content

    def heartbeat(self, uuid, advertise_address, advertise_protocol='http',
                  generated_cert=None):
        path = self.heartbeat_api.format(uuid=uuid)

        data = {'callback_url': self._get_agent_url(advertise_address, uuid,
                                                    advertise_protocol)}

        api_ver = self._get_ironic_api_version()

        if api_ver >= AGENT_TOKEN_IRONIC_VERSION:
            data['agent_token'] = self.agent_token

        if api_ver >= AGENT_VERSION_IRONIC_VERSION:
            data['agent_version'] = __version__

        if api_ver >= AGENT_VERIFY_CA_IRONIC_VERSION and generated_cert:
            data['agent_verify_ca'] = generated_cert

        api_ver = min(MAX_KNOWN_VERSION, api_ver)
        headers = self._get_ironic_api_version_header(api_ver)

        self._logger.debug(
            'Heartbeat: announcing callback URL %s,'
            'API version is %d.%d',
            data['callback_url'], *api_ver)

        headers['Connection'] = 'close'
        try:
            response = self._request('POST', path, data=data, headers=headers)
        except requests.exceptions.ConnectionError as e:
            raise error.HeartbeatConnectionError(str(e))
        except Exception as e:
            raise error.HeartbeatError(str(e))

        if response.status_code == requests.codes.CONFLICT:
            err = self._error_from_response(response)
            raise error.HeartbeatConflictError(err)
        elif response.status_code == requests.codes.NOT_FOUND:
            err = self._error_from_response(response)
            raise error.HeartbeatNotFoundError(err)
        elif response.status_code != requests.codes.ACCEPTED:
            err = self._error_from_response(response)
            raise error.HeartbeatError(err)

    def _get_agent_url(self, advertise_address, uuid,
                       advertise_protocol='http'):
        return '{}://{}:{}/{}'.format(advertise_protocol,
                                      advertise_address[0],
                                      advertise_address[1], uuid)

def get_ssl_client_options(conf):

    if conf.get('FAKE_IPA_INSECURE'):
        verify = False
    else:
        verify = conf.get("FAKE_IPA_CAFILE") or True
    if conf.get("FAKE_IPA_CERTFILE") and conf.get("FAKE_IPA_KEYFILE"):
        cert = (conf.get("FAKE_IPA_CERTFILE"), conf.get("FAKE_IPA_KEYFILE"))
    else:
        cert = None

    return verify, cert
