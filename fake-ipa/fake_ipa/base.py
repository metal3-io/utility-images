#!/usr/bin/python3
# Copyright 2013 Rackspace, Inc.
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

import collections
import functools
from importlib import import_module
import inspect
import logging
import random
import threading
import time
import uuid

from fake_ipa import encoding
from fake_ipa import error


LOG = logging.getLogger(__name__)


class BaseAgentExtension:
    def __init__(self, agent=None):
        self.agent = agent
        self.command_map = dict(
            (v.command_name, v)
            for _, v in inspect.getmembers(self)
            if hasattr(v, 'command_name')
        )

    def execute(self, command_name, **kwargs):
        cmd = self.command_map.get(command_name)
        if cmd is None:
            raise error.InvalidCommandError(
                'Unknown command: {}'.format(command_name))
        return cmd(**kwargs)

    def check_cmd_presence(self, ext_obj, ext, cmd):
        if not (hasattr(ext_obj, 'execute')
                and hasattr(ext_obj, 'command_map')
                and cmd in ext_obj.command_map):
            raise error.InvalidCommandParamsError(
                "Extension {} doesn't provide {} method".format(ext, cmd))

    def fake_processing_delay(self, min, max):
        processing_time = random.randint(min, max)
        time.sleep(processing_time)


class AgentCommandStatus(object):
    """Mapping of agent command statuses."""
    RUNNING = 'RUNNING'
    SUCCEEDED = 'SUCCEEDED'
    FAILED = 'FAILED'
    # TODO(dtantsur): keeping the same text for backward compatibility, change
    # to just VERSION_MISMATCH one release after ironic is updated.
    VERSION_MISMATCH = 'CLEAN_VERSION_MISMATCH'


class BaseCommandResult(encoding.SerializableComparable):
    """Base class for command result."""

    serializable_fields = ('id', 'command_name',
                           'command_status', 'command_error', 'command_result')

    def __init__(self, command_name, command_params):
        """Construct an instance of BaseCommandResult.

        :param command_name: name of command executed
        :param command_params: parameters passed to command
        """

        self.id = str(uuid.uuid4())
        self.command_name = command_name
        self.command_params = command_params
        self.command_status = AgentCommandStatus.RUNNING
        self.command_error = None
        self.command_result = None

    def __str__(self):
        return ("Command name: %(name)s, "
                "params: %(params)s, status: %(status)s, result: "
                "%(result)s." %
                {"name": self.command_name,
                 "params": self.command_params,
                 "status": self.command_status,
                 "result": self.command_result})

    def is_done(self):
        """Checks to see if command is still RUNNING.

        :returns: True if command is done, False if still RUNNING
        """
        return self.command_status != AgentCommandStatus.RUNNING

    def join(self):
        """:returns: result of completed command."""
        return self

    def wait(self):
        """Join the result and extract its value.

        Raises if the command failed.
        """
        self.join()
        if self.command_error is not None:
            raise self.command_error
        else:
            return self.command_result


class SyncCommandResult(BaseCommandResult):
    """A result from a command that executes synchronously."""

    def __init__(self, command_name, command_params, success, result_or_error):
        """Construct an instance of SyncCommandResult.

        :param command_name: name of command executed
        :param command_params: parameters passed to command
        :param success: True indicates success, False indicates failure
        :param result_or_error: Contains the result (or error) from the command
        """

        super(SyncCommandResult, self).__init__(command_name,
                                                command_params)
        if isinstance(result_or_error, (bytes, str)):
            result_key = 'result' if success else 'error'
            result_or_error = {result_key: result_or_error}

        if success:
            self.command_status = AgentCommandStatus.SUCCEEDED
            self.command_result = result_or_error
        else:
            self.command_status = AgentCommandStatus.FAILED
            self.command_error = result_or_error


class AsyncCommandResult(BaseCommandResult):
    """A command that executes asynchronously in the background."""

    def __init__(self, command_name, command_params, execute_method,
                 agent=None):
        """Construct an instance of AsyncCommandResult.

        :param command_name: name of command to execute
        :param command_params: parameters passed to command
        :param execute_method: a callable to be executed asynchronously
        :param agent: Optional: an instance of IronicPythonAgent
        """

        super(AsyncCommandResult, self).__init__(command_name, command_params)
        self.agent = agent
        self.execute_method = execute_method
        self.time = time.time() + random.randint(5, 10)

    def join(self, timeout=None):
        """Block until command has completed, and return result.

        :param timeout: float indicating max seconds to wait for command
                        to complete. Defaults to None.
        """
        time.sleep(max(0, self.time - time.time()))
        return self

    def run(self):
        """Run a command."""

        try:
            result = self.execute_method(**self.command_params)
            self.command_result = result
            self.command_status = AgentCommandStatus.SUCCEEDED

        except Exception as e:
            LOG.exception('Command failed: %(name)s, error: %(err)s',
                          {'name': self.command_name, 'err': e})
            if not isinstance(e, error.RESTError):
                e = error.CommandExecutionError(str(e))

            self.command_error = e
            self.command_status = AgentCommandStatus.FAILED
        finally:
            if self.agent:
                self.agent.force_heartbeat()


class ExecuteCommandMixin(object):
    def __init__(self):
        self.command_lock = threading.Lock()
        self.command_results = collections.OrderedDict()

    def get_extension(self, extension_name):

        extensions_list = {
            "standby": "fake_ipa.standby.StandbyExtension",
            "clean": "fake_ipa.clean.CleanExtension",
            "deploy": "fake_ipa.deploy.DeployExtension",
            "image": "fake_ipa.image.ImageExtension",
            "log": "fake_ipa.log.LogExtension"
        }

        if extension_name not in extensions_list:
            raise error.ExtensionError(
                'Extension %s does not exist !', extension_name
            )
        try:
            ext_path, ext_class = extensions_list[extension_name].rsplit(
                ".", 1
            )
        except ValueError:
            raise error.ExtensionError(
                '%s extension path error' % extensions_list[extension_name]
            )

        module = import_module(ext_path)
        return getattr(module, ext_class)()

    def split_command(self, command_name):
        command_parts = command_name.split('.', 1)
        if len(command_parts) != 2:
            raise error.InvalidCommandError(
                'Command name must be of the form <extension>.<name>')

        return (command_parts[0], command_parts[1])

    def refresh_last_async_command(self):
        if len(self.command_results) > 0:
            last_command = list(self.command_results.values())[-1]
            if not last_command.is_done() and time.time() >= last_command.time:
                last_command.run()

    def execute_command(self, command_name, **kwargs):
        """Execute an agent command."""
        self.refresh_last_async_command()
        LOG.debug(
            'Executing command: %(name)s with args: %(args)s',
            {
                'name': command_name,
                'args': kwargs
            })
        extension_part, command_part = self.split_command(command_name)

        if len(self.command_results) > 0:
            last_command = list(self.command_results.values())[-1]
            if not last_command.is_done():
                LOG.error(
                    'Tried to execute %(command)s, agent is still '
                    'executing %(last)s',
                    {
                        'command': command_name,
                        'last': last_command
                    })
                raise error.AgentIsBusy(last_command.command_name)

        try:
            ext = self.get_extension(extension_part)
            result = ext.execute(command_part, **kwargs)
        except KeyError:
            # Extension Not found
            LOG.exception('Extension %s not found', extension_part)
            raise error.RequestedObjectNotFoundError(
                'Extension',
                extension_part)
        except error.InvalidContentError as e:
            # Any command may raise a InvalidContentError which will be
            # returned to the caller directly.
            LOG.exception('Invalid content error: %s', e)
            raise e
        except Exception as e:
            # Other errors are considered command execution errors, and are
            # recorded as a failed SyncCommandResult with an error message
            LOG.exception('Command execution error: %s', e)
            result = SyncCommandResult(command_name, kwargs, False, e)
        self.command_results[result.id] = result
        return result


def async_command(command_name, validator=None):
    """Will run the command in an AsyncCommandResult in its own thread.

    command_name is set based on the func name and command_params will
    be whatever args/kwargs you pass into the decorated command.
    Return values of type `str` or `unicode` are prefixed with the
    `command_name` parameter when returned for consistency.
    """

    def async_decorator(func):
        func.command_name = command_name

        @functools.wraps(func)
        def wrapper(self, **command_params):
            # Run a validator before passing everything off to async.
            # validators should raise exceptions or return silently.
            if validator:
                validator(self, **command_params)

            # bind self to func so that AsyncCommandResult doesn't need to
            # know about the mode
            bound_func = functools.partial(func, self)
            ret = AsyncCommandResult(command_name,
                                     command_params,
                                     bound_func,
                                     agent=self.agent)
            LOG.info('Asynchronous command %(name)s started execution',
                     {'name': command_name})
            return ret
        return wrapper
    return async_decorator


def sync_command(command_name, validator=None):
    """Decorate a method to wrap its return value in a SyncCommandResult.

    For consistency with @async_command() can also accept a
    validator which will be used to validate input, although a synchronous
    command can also choose to implement validation inline.
    """

    def sync_decorator(func):
        func.command_name = command_name

        @functools.wraps(func)
        def wrapper(self, **command_params):
            # Run a validator before invoking the function.
            # validators should raise exceptions or return silently.
            if validator:
                validator(self, **command_params)

            result = func(self, **command_params)
            LOG.info('Synchronous command %(name)s completed: %(result)s',
                     {'name': command_name,
                      'result': result})
            return SyncCommandResult(command_name,
                                     command_params,
                                     True,
                                     result)

        return wrapper
    return sync_decorator
