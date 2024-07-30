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

import collections
import random
from threading import currentThread
from threading import Thread
import time

from fake_ipa import error

Host = collections.namedtuple('Host', ['hostname', 'port'])


class Heatbeater:

    queue = collections.deque()
    remove_from_q = set()
    interval = 0
    heartbeat_forced = False

    @classmethod
    def initialize(cls, config, logger):
        cls._config = config
        cls._logger = logger
        return cls

    # If we could wait at most N seconds between heartbeats (or in case of an
    # error) we will instead wait r x N seconds, where r is a random value
    # between these multipliers.
    min_jitter_multiplier = 0.3
    max_jitter_multiplier = 0.6
    min_interval = 5

    def heartbeat(self):
        while True:

            try:
                (system, agent, previous_heartbeat) = \
                    Heatbeater.queue.popleft()
                if system['uuid'] in Heatbeater.remove_from_q:
                    self._logger.info(
                        'Thread[%s] Removing.. %s ', currentThread().ident,
                        system['name'])
                    Heatbeater.remove_from_q.remove(system['uuid'])
                    Heatbeater.min_interval = 5
                    continue
            except IndexError:
                # empty q default min interval supposing:
                # len(thread) << len(nodes)
                # else thread q != no node in heartbeater
                Heatbeater.min_interval = 5
                time.sleep(Heatbeater.min_interval)
                continue

            if self._heartbeat_expected(agent, previous_heartbeat):
                self._logger.debug(
                    'Thread[%s] Currently processing %s'
                    '[%s] and  %s ',
                    currentThread().ident, system['name'],
                    system['uuid'], Heatbeater.printq())
                self.do_heartbeat(system, agent)
                Heatbeater.queue.append((system, agent, time.time()))
            else:

                Heatbeater.queue.append((system, agent, previous_heartbeat))

            time.sleep(self.min_interval)

    def _heartbeat_expected(self, agent, previous_heartbeat):
        # Normal heartbeating
        if time.time() > previous_heartbeat + agent.heartbeater.interval:
            return True

        # Forced heartbeating, but once in 5 seconds
        if (agent.heartbeater.heartbeat_forced
                and time.time() > previous_heartbeat + 5):
            return True

    def do_heartbeat(self, system, agent):
        """Send a heartbeat to Ironic."""
        try:
            agent.api_client.heartbeat(
                uuid=agent.node['uuid'],
                advertise_address=Host(
                    hostname=self._config['FAKE_IPA_ADVERTISE_ADDRESS_IP'],
                    port=self._config['FAKE_IPA_ADVERTISE_ADDRESS_PORT']),
                advertise_protocol="http",
                generated_cert=None,
            )
            self._logger.info('heartbeat successful')
            agent.heartbeater.heartbeat_forced = False
            self.previous_heartbeat = time.time()
        except error.HeartbeatConflictError:
            self._logger.warning('conflict error sending heartbeat to %s',
                                 agent.api_url)
        except error.HeartbeatNotFoundError:
            self._logger.warning(
                'not found error removing the node from'
                'heartbeater q %s',
                system["uuid"])
            Heatbeater.remove_from_heartbeater_q(system["uuid"])
        except Exception:
            self._logger.exception(
                'error sending heartbeat to %s', agent.api_url)
        finally:
            interval_multiplier = random.uniform(
                agent.heartbeater.min_jitter_multiplier,
                agent.heartbeater.max_jitter_multiplier)
            agent.heartbeater.interval = \
                agent.heartbeat_timeout * interval_multiplier
            Heatbeater.min_interval = min(agent.heartbeater.interval, 5)
            self._logger.info(
                'sleeping before next heartbeat, interval: %s'
                '(min interval %s)',
                agent.heartbeater.interval,
                Heatbeater.min_interval)

    def force_heartbeat(self):
        self.heartbeat_forced = True

    @classmethod
    def remove_from_heartbeater_q(cls, uuid):
        # to avoid conflicts with threads only the threads heartbeating
        # the node can remove it in this method we create a temporary list
        # for the nodes to be removed
        # TODO(Mohammed) add expire time so if node left out in this list
        # we clean them periodically
        Heatbeater._logger.info("Added to remove list %s", uuid)
        Heatbeater.remove_from_q.add(uuid)

    @classmethod
    def printq(cls):
        _l = []
        for _q in Heatbeater.queue:
            node_name = _q[0]['name']
            time_left = _q[2] + \
                _q[1].heartbeater.interval - time.time()
            if _q[0]['uuid'] in Heatbeater.remove_from_q:
                node_name = "X" + node_name + "X"
            _l.append("{0} <- {1:.0f}s".format(node_name, time_left))
        return {"Q": _l, "To be removed": Heatbeater.remove_from_q}

    @classmethod
    def add_to_q(cls, system, agent):
        # when we inspect an on node it will be added to removing list before
        #  turning off
        if system['uuid'] in Heatbeater.remove_from_q:
            Heatbeater.remove_from_q.remove(system['uuid'])
        Heatbeater.queue.append((system, agent, time.time()))

    @classmethod
    def run_heartbeater_threads(cls, nb_threads):
        # Setup the heartbeater threads
        threads = [Thread(target=Heatbeater().heartbeat, daemon=True)
                   for _ in range(nb_threads)]
        for t in threads:
            t.start()
