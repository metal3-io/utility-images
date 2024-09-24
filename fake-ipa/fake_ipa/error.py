#!/usr/bin/python3
# Copyright 2018 Red Hat, Inc.
# Copyright 2024 Ericsson Software Technology
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


from fake_ipa import encoding


class FishyError(Exception):
    """Create generic sushy-tools exception object"""

    def __init__(self, msg='Unknown error', code=500):
        super().__init__(msg)
        self.code = code


class AliasAccessError(FishyError):
    """Node access attempted via an alias, not UUID"""


class NotSupportedError(FishyError):
    """Feature not supported by resource driver"""

    def __init__(self, msg='Unsupported'):
        super().__init__(msg)


class NotFound(FishyError):
    """Entity not found."""

    def __init__(self, msg='Not found', code=404):
        super().__init__(msg, code)


class BadRequest(FishyError):
    """Malformed request."""

    def __init__(self, msg, code=400):
        super().__init__(msg, code)


class FeatureNotAvailable(NotFound):
    """Feature is not available."""

    def __init__(self, feature, code=404):
        super().__init__(f"Feature {feature} not available", code=code)


class Conflict(FishyError):
    """Conflict with current state of the resource."""

    def __init__(self, msg, code=409):
        super().__init__(msg, code)

class LookupNodeError(Exception):
    """Error raised when the node lookup to the Ironic API fails."""

    def __init__(self, msg='Error getting configuration from Ironic'):
        super().__init__(msg)


class RESTError(Exception, encoding.Serializable):
    """Base class for errors generated in ironic-python-client."""
    message = 'An error occurred'
    details = 'An unexpected error occurred. Please try back later.'
    status_code = 500
    serializable_fields = ('type', 'code', 'message', 'details')

    def __init__(self, details=None, *args, **kwargs):
        super(RESTError, self).__init__(*args, **kwargs)
        self.type = self.__class__.__name__
        self.code = self.status_code
        if details:
            self.details = details

    def __str__(self):
        return "{}: {}".format(self.message, self.details)

    def __repr__(self):
        """Should look like RESTError('message: details')"""
        return "{}('{}')".format(self.__class__.__name__, self.__str__())


class IronicAPIError(RESTError):
    """Error raised when a call to the agent API fails."""

    message = 'Error in call to ironic-api'

    def __init__(self, details):
        super(IronicAPIError, self).__init__(details)


class NodeUUIDError(IronicAPIError):
    """Error raised when UUID key does not exist in agents dict."""

    message = 'Error UUID does not exist'

    def __init__(self, details):
        super(NodeUUIDError, self).__init__(details)


class HeartbeatError(IronicAPIError):
    """Error raised when a heartbeat to the agent API fails."""

    message = 'Error heartbeating to agent API'

    def __init__(self, details):
        super(HeartbeatError, self).__init__(details)


class HeartbeatNotFoundError(IronicAPIError):
    """Error raised when a heartbeat to the agent API fails."""

    message = 'Error heartbeating to agent API'

    def __init__(self, details):
        super(HeartbeatNotFoundError, self).__init__(details)


class HeartbeatConflictError(IronicAPIError):
    """ConflictError raised when a heartbeat to the agent API fails."""

    message = 'ConflictError heartbeating to agent API'

    def __init__(self, details):
        super(HeartbeatConflictError, self).__init__(details)


class HeartbeatConnectionError(IronicAPIError):
    """Transitory connection failure occured attempting to contact the API."""

    message = ("Error attempting to heartbeat - Possible transitory network "
               "failure or blocking port may be present.")

    def __init__(self, details):
        super(HeartbeatConnectionError, self).__init__(details)


class CommandExecutionError(RESTError):
    """Error raised when a command fails to execute."""

    message = 'Command execution failed'

    def __init__(self, details):
        super(CommandExecutionError, self).__init__(details)


class AgentIsBusy(CommandExecutionError):

    message = 'Agent is busy'
    status_code = 409

    def __init__(self, command_name):
        super().__init__('executing command %s' % command_name)


class RequestedObjectNotFoundError(NotFound):
    def __init__(self, type_descr, obj_id):
        details = '{} with id {} not found.'.format(type_descr, obj_id)
        super(RequestedObjectNotFoundError, self).__init__(details)


class InvalidContentError(RESTError):
    """Error which occurs when a user supplies invalid content.

    Either because that content cannot be parsed according to the advertised
    `Content-Type`, or due to a content validation error.
    """

    message = 'Invalid request body'
    status_code = 400

    def __init__(self, details):
        super(InvalidContentError, self).__init__(details)


class ExtensionError(RESTError):
    pass


class InvalidCommandError(InvalidContentError):
    """Error which is raised when an unknown command is issued."""

    message = 'Invalid command'

    def __init__(self, details):
        super(InvalidCommandError, self).__init__(details)


class InvalidCommandParamsError(InvalidContentError):
    """Error which is raised when command parameters are invalid."""

    message = 'Invalid command parameters'

    def __init__(self, details):
        super(InvalidCommandParamsError, self).__init__(details)


class VersionMismatch(RESTError):
    """Error raised when Ironic and the Agent have different versions.

    If the agent version has changed since get_clean_steps or get_deploy_steps
    was called by the Ironic conductor, it indicates the agent has been updated
    (either on purpose, or a new agent was deployed and the node was rebooted).
    Since we cannot know if the upgraded IPA will work with cleaning/deploy as
    it stands (steps could have different priorities, either in IPA or in
    other Ironic interfaces), we should restart the process from the start.
    """
    message = (
        'Hardware managers version mismatch, reload agent with correct version'
    )

    def __init__(self, agent_version, node_version):
        self.status_code = 409
        details = ('Current versions: {}, versions used by ironic: {}'
                   .format(agent_version, node_version))
        super(VersionMismatch, self).__init__(details)
