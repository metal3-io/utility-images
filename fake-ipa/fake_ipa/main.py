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

import argparse
import logging
import sys
from threading import Thread

from flask import Flask
from flask import json
from flask import request
from werkzeug.exceptions import HTTPException
from werkzeug.exceptions import Unauthorized
from werkzeug import Response


from fake_ipa import encoding
from fake_ipa.fake_agent import FakeIronicPythonAgent
from fake_ipa.heartbeater import Heatbeater


class Application(Flask):
    agents = {}
    booted_q = set()


app = Application(__name__)
app.logger.setLevel(logging.DEBUG)

@app.errorhandler(HTTPException)
def handle_exception(e):
    """Return JSON instead of HTML for HTTP errors."""

    # start with the correct headers and status code from the error
    response = e.get_response()
    # replace the body with JSON
    response.data = json.dumps({
        "code": e.code,
        "name": e.name,
        "description": e.description,
    })
    response.content_type = "application/json"
    return response


@app.route('/', methods=['PUT'])
def notification_handler():
    """
    Endpoint to receive notifications about Systems power state updates

    This function receives a JSON representing a system's current state
    It boot or destroy FakeIPA for a sytem based on the pending power state
    recieved

    Example System JSON:
    {
        "uuid": "27946b59-9e44-4fa7-8e91-f3527a1ef094",
        "name": "fake1",
        "power_state": "On",
        ...
        "boot_device": "Pxe",
        "pending_power": {
            "power_state": "Off",
            "apply_time": 1720787353
        }
    }

    Processing Logic:
    1. If the 'pending_power' field is missing or empty, no action is taken.
    2. If 'pending_power.power_state' is 'On':
        a. If the system is not already booted, it will be added to the boot queue
           and the boot process will start after the delay specified by 'apply_time'.
    3. If 'pending_power.power_state' is not 'On':
        a. If the system is currently booted, it will be removed from the boot queue
           and shutdown IPA after the delay specified by 'apply_time'.

    Note:
    - If the system is already powered on or off, duplicate 'pending_power' state updates
      should be ignored.
    """
    system = request.json
    system_name = system.get('name', 'unknown')
    app.logger.info("Received system update for %s: %s", system_name, system)

    # Check if 'pending_power' is present and not None or empty
    if 'pending_power' not in system or not system['pending_power']:
        # No action
        app.logger.info("No pending power state. No action taken for system: %s", system_name)
        return '', 204

    pending_power_state = system['pending_power']['power_state']

    if pending_power_state == 'On':
        app.logger.info("Pending power state is 'On' for system: %s", system_name)
        # If the system is not already booted and the boot device is not 'Hdd', initiate boot process
        if not is_booted(system) and system['boot_device'] != 'Hdd':
            app.logger.info("Boot IPA for System %s.", system_name)
            app.booted_q.add(system['uuid'])
            boot(system)
        else:
            app.logger.info("System %s is already booted or boot device is 'Hdd'. No boot action taken.", system_name)
    else:
        app.logger.info("Pending power state is 'Off' or other state for system: %s", system_name)
        # If the system is currently booted, initiate destruction process
        if is_booted(system):
            app.logger.info("Shutdown IPA for System %s", system_name)
            app.booted_q.remove(system['uuid'])
            remove_from_heartbeater(system['uuid'])
    return '', 204

def is_booted(system):
    return system['uuid'] in app.booted_q

def boot(system):
    # init agent if not already done
    if not hasattr(FakeIronicPythonAgent, 'api'):
        FakeIronicPythonAgent.initialize(app.config, app.logger, app)
    ipa = FakeIronicPythonAgent(system, app.config.get(
        'FAKE_IPA_API_URL', 'http://localhost:6385'))
    thread = Thread(target=ipa.boot, daemon=True)
    thread.start()


def remove_from_heartbeater(uuid):
    # init agent if not already done
    if not hasattr(FakeIronicPythonAgent, 'api'):
        FakeIronicPythonAgent.initialize(app.config, app.logger, app)
    Heatbeater.remove_from_heartbeater_q(uuid)


# IPA API
_DOCS_URL = 'https://docs.openstack.org/ironic-python-agent'
_CUSTOM_MEDIA_TYPE = 'application/vnd.openstack.ironic-python-agent.v1+json'


def jsonify(value, status=200):
    """Convert value to a JSON response using the custom encoder."""

    encoder = encoding.RESTJSONEncoder()
    data = encoder.encode(value)
    return Response(data, status=status, mimetype='application/json')


def make_link(url, rel_name, resource='', resource_args='',
              bookmark=False, type_=None):
    if rel_name == 'describedby':
        url = _DOCS_URL
        type_ = 'text/html'
    elif rel_name == 'bookmark':
        bookmark = True

    template = ('%(root)s/%(resource)s' if bookmark
                else '%(root)s/v1/%(resource)s')
    template += ('%(args)s'
                 if resource_args.startswith('?') or not resource_args
                 else '/%(args)s')

    result = {'href': template % {'root': url,
                                  'resource': resource,
                                  'args': resource_args},
              'rel': rel_name}
    if type_:
        result['type'] = type_
    return result


def version(url):
    return {
        'id': 'v1',
        'links': [
            make_link(url, 'self', 'v1', bookmark=True),
            make_link(url, 'describedby', bookmark=True),
        ],
    }


@app.route('/<uuid>/', methods=['GET'])
def api_root(uuid):
    url = request.url_root.rstrip('/')
    return jsonify({
        'name': 'OpenStack Ironic Fake Python Agent API',
        'description': ('Ironic Fake Python Agent is a '
                        'fake provisioning agent for '
                        'OpenStack Ironic'),
        'versions': [version(url)],
        'default_version': version(url),
        })


@app.route('/<uuid>/v1/', methods=['GET'])
def api_v1(uuid):
    url = request.url_root.rstrip('/')
    return jsonify(dict({
        'commands': [
            make_link(url, 'self', 'commands'),
            make_link(url, 'bookmark', 'commands'),
        ],
        'status': [
            make_link(url, 'self', 'status'),
            make_link(url, 'bookmark', 'status'),
        ],
        'media_types': [
            {'base': 'application/json',
                'type': _CUSTOM_MEDIA_TYPE},
        ],
    }, **version(url)))


@app.route('/<uuid>/v1/commands/', methods=['GET'])
def api_list_commands(uuid):
    try:
        results = app.agents[uuid].list_command_results()
    except KeyError:
        pass
    return jsonify({'commands': results})


@app.route('/<uuid>/v1/commands/<cmd>', methods=['GET'])
def api_get_command(uuid, cmd):
    result = app.agents[uuid].get_command_result(cmd)
    wait = request.args.get('wait')

    if wait and wait.lower() == 'true':
        result.join()

    return jsonify(result)


@app.route('/<uuid>/v1/commands/', methods=['POST'])
def api_run_command(uuid):
    body = request.get_json(force=True)
    if ('name' not in body or 'params' not in body
            or not isinstance(body['params'], dict)):
        raise HTTPException.BadRequest('Missing or invalid name or params')

    token = request.args.get('agent_token', None)
    if not app.agents[uuid].validate_agent_token(token):
        raise Unauthorized('Token invalid.')
    # get uuid
    result = app.agents[uuid].execute_command(
        body['name'], **body['params'])
    wait = request.args.get('wait')
    if wait and wait.lower() == 'true':
        result.join()
    return jsonify(result)


def parse_args():
    parser = argparse.ArgumentParser('sushy-fake-ipa')
    parser.add_argument('--config',
                        type=str,
                        help='Config file path. Can also be set via '
                             'environment variable SUSHY_FAKE_IPA_CONFIG.')
    parser.add_argument('-i', '--interface',
                        type=str,
                        help='IP address of the local interface to listen '
                        'at. Can also be set via config variable '
                        'SUSHY_FAKE_IPA_LISTEN_IP. Default is all '
                        'local interfaces.')
    parser.add_argument('-p', '--port',
                        type=int,
                        help='TCP port to bind the server to.  Can also be '
                        'set via config variable '
                        'SUSHY_FAKE_IPA_LISTEN_PORT. Default is 9999.')
    return parser.parse_args()


def main():
    args = parse_args()
    app.config.from_pyfile(args.config)
    DEFAULT_PORT = 9999
    if not app.config.get('FAKE_IPA_ADVERTISE_ADDRESS_IP'):
        app.logger.error(
            'Please set FAKE_IPA_ADVERTISE_ADDRESS_IP in config file'
            )
        return 1
    if not app.config.get('FAKE_IPA_ADVERTISE_ADDRESS_PORT'):
        app.config.setdefault('FAKE_IPA_ADVERTISE_ADDRESS_PORT', DEFAULT_PORT)

    app.logger.info(
        'FAKE_IPA_ADVERTISE_ADDRESS_IP: %s',
        app.config.get('FAKE_IPA_ADVERTISE_ADDRESS_IP')
        )
    app.run(host=app.config.get('SUSHY_FAKE_IPA_LISTEN_IP', '0.0.0.0'),
            port=app.config.get('SUSHY_FAKE_IPA_LISTEN_PORT', DEFAULT_PORT),
            debug=True)

    return 0

if __name__ == '__main__':
    sys.exit(main())
