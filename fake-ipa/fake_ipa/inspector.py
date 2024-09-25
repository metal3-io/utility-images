#!/usr/bin/python3
# Copyright 2015 Red Hat, Inc.
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

import requests
import tenacity

_RETRY_WAIT = 5
_RETRY_ATTEMPTS = 5

# FIXME fix passing the logger as parameter


def inspect(system, inspection_callback_url, verify, cert, logger):

    data = {
        "boot_interface": system.get("nics")[0]["mac"],
        "inventory": {
            "interfaces": [
                {
                    "lldp": None,
                    "product": "0x0001",
                    "vendor": "0x1af4",
                    "name": nic.get("name", f"enp{i+1}s0"),
                    "has_carrier": True,
                    "ipv4_address": nic.get("ip"),
                    "client_id": None,
                    "mac_address": nic.get("mac"),
                }
                for i, nic in enumerate(system.get("nics"))
            ],
            "cpu": {
                "count": 2,
                "frequency": "2100.084",
                "flags": ["fpu", "mmx", "fxsr", "sse", "sse2"],
                "architecture": "x86_64",
            },
        },
    }

    @tenacity.retry(
        retry=tenacity.retry_if_exception_type(
            requests.exceptions.ConnectionError),
        stop=tenacity.stop_after_attempt(_RETRY_ATTEMPTS),
        wait=tenacity.wait_fixed(_RETRY_WAIT),
        reraise=True)
    def _post_to_inspector():
        return requests.post(inspection_callback_url, verify=verify, cert=cert, json=data)

    resp = _post_to_inspector()
    if resp.status_code >= 400:
        logger.error('inspector %s error %d: %s, proceeding with lookup',
                     inspection_callback_url,
                     resp.status_code, resp.content.decode('utf-8'))
        return

    return resp.json().get('uuid')
