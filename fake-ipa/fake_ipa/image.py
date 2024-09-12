#!/usr/bin/python3
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import logging

from fake_ipa import base

LOG = logging.getLogger(__name__)


class ImageExtension(base.BaseAgentExtension):

    @base.async_command('install_bootloader')
    def install_bootloader(self, root_uuid, efi_system_part_uuid=None,
                           prep_boot_part_uuid=None,
                           target_boot_mode='bios',
                           ignore_bootloader_failure=None):
        """Install the GRUB2 bootloader on the image.

        :param root_uuid: The UUID of the root partition.
        :param efi_system_part_uuid: The UUID of the efi system partition.
            To be used only for uefi boot mode.  For uefi boot mode, the
            boot loader will be installed here.
        :param prep_boot_part_uuid: The UUID of the PReP Boot partition.
            Used only for booting ppc64* partition images locally. In this
            scenario the bootloader will be installed here.
        :param target_boot_mode: bios, uefi. Only taken into account
            for softraid, when no efi partition is explicitely provided
            (happens for whole disk images)

        """
        LOG.debug('Executing image install_bootloader')
        return
