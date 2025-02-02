# #######
# Copyright (c) 2014-2020 Cloudify Platform Ltd. All rights reserved
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#        http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from os.path import basename
import re

from cloudify import ctx
from cloudify.decorators import operation
from cloudify.exceptions import NonRecoverableError
from .. import _compat
from .. import utils
from .. import constants
from .keypair import KeyPair
from ..gcp import (
        GCPError,
        check_response,
        GoogleCloudPlatform,
        )

PS_OPEN = '<powershell>'
PS_CLOSE = '</powershell>'
POWERSHELL_SCRIPTS = ['sysprep-specialize-script-ps1',
                      'windows-startup-script-ps1']


class Instance(GoogleCloudPlatform):
    ACCESS_CONFIG = 'External NAT'
    ACCESS_CONFIG_TYPE = 'ONE_TO_ONE_NAT'
    NETWORK_INTERFACE = 'nic0'
    STANDARD_MACHINE_TYPE = 'n1-standard-1'
    DEFAULT_SCOPES = ['https://www.googleapis.com/auth/devstorage.read_write',
                      'https://www.googleapis.com/auth/logging.write']

    def __init__(self,
                 config,
                 logger,
                 name,
                 additional_settings=None,
                 image=None,
                 disks=None,
                 machine_type=None,
                 startup_script=None,
                 external_ip=False,
                 tags=None,
                 scopes=None,
                 ssh_keys=None,
                 network=None,
                 subnetwork=None,
                 zone=None,
                 can_ip_forward=False,
                 ):
        """
        Create Instance object

        :param config: gcp auth file
        :param logger: logger object
        :param name: name of the instance
        :param image: image id in Google Cloud Platform
        :param machine_type: machine type on GCP, default None
        :param startup_script: shell script text to be run on instance startup,
        default None
        :param external_ip: boolean external ip indicator, default False
        :param tags: tags for the instance, default []
        """
        super(Instance, self).__init__(
            config,
            logger,
            utils.get_gcp_resource_name(name),
            additional_settings)
        self.image = image
        self.machine_type = machine_type
        self.startup_script = startup_script
        self.tags = tags + [self.name] if tags else [self.name]
        self.externalIP = external_ip
        self.disks = disks or []
        self.scopes = scopes or self.DEFAULT_SCOPES
        self.ssh_keys = ssh_keys or []
        self.zone = zone
        self.network = network
        self.subnetwork = subnetwork
        self.can_ip_forward = can_ip_forward

    @utils.sync_operation
    @check_response
    def set_machine_type(self, name, zone, machine_type):
        """
        Set machine type GCP instance.
        Zone operation.

        :return: REST response with operation responsible for the instance
        set machine type process and its status
        """
        self.logger.info('Set machine type instance {0}'.format(self.name))
        full_machine_type = "{0}/machineTypes/{1}".format(
            zone, machine_type)
        return self.discovery.instances().setMachineType(
            project=self.project,
            zone=basename(zone),
            instance=name,
            body={'machineType': full_machine_type}).execute()

    @utils.sync_operation
    @check_response
    def stop(self):
        """
        Stop GCP instance.
        Zone operation.

        :return: REST response with operation responsible for the instance
        stop process and its status
        """
        self.logger.info('Stop instance {0}'.format(self.name))
        return self.discovery.instances().stop(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name).execute()

    @utils.sync_operation
    @check_response
    def start(self):
        """
        Start GCP instance.
        Zone operation.

        :return: REST response with operation responsible for the instance
        Start process and its status
        """
        self.logger.info('Start instance {0}'.format(self.name))
        return self.discovery.instances().start(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name).execute()

    @utils.async_operation(get=True)
    @check_response
    def create(self):
        """
        Create GCP VM instance with given parameters.
        Zone operation.

        :return: REST response with operation responsible for the instance
        creation process and its status
        :raise: GCPError if there is any problem with startup script file:
        e.g. the file is not under the given path or it has wrong permissions
        """

        disk = ctx.instance.runtime_properties.get(constants.DISK)
        if disk:
            self.disks = [disk]
        if not self.disks and not self.image:
            raise NonRecoverableError("A disk image ID must be provided")

        return self.discovery.instances().insert(
            project=self.project,
            zone=basename(self.zone),
            body=self.to_dict()).execute()

    @utils.async_operation()
    @check_response
    def delete(self):
        """
        Delete GCP instance.
        Zone operation.

        :return: REST response with operation responsible for the instance
        deletion process and its status
        """
        self.logger.info('Delete instance {0}'.format(self.name))
        return self.discovery.instances().delete(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name).execute()

    @check_response
    def set_tags(self, tags):
        """
        Set GCP instance tags.
        Zone operation.

        :return: REST response with operation responsible for the instance
        tag setting process and its status
        """
        # each tag should be RFC1035 compliant
        self.logger.info(
            'Set tags {0} to instance {1}'.format(str(tags), self.name))
        tag_dict = self.get()['tags']
        self.tags = tag_dict.get('items', [])
        self.tags.extend(tags)
        self.tags = list(set(self.tags))
        fingerprint = tag_dict['fingerprint']
        return self.discovery.instances().setTags(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name,
            body={'items': self.tags, 'fingerprint': fingerprint}).execute()

    @check_response
    def remove_tags(self, tags):
        """
        Remove GCP instance tags.
        Zone operation.

        :return: REST response with operation responsible for the instance
        tag removal process and its status
        """
        # each tag should be RFC1035 compliant
        self.logger.info(
            'Remove tags {0} from instance {1}'.format(
                str(self.tags),
                self.name))
        tag_dict = self.get()['tags']
        self.tags = tag_dict.get('items', [])

        self.tags = [tag for tag in self.tags if tag not in tags]
        fingerprint = tag_dict['fingerprint']
        return self.discovery.instances().setTags(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name,
            body={'items': self.tags, 'fingerprint': fingerprint}).execute()

    @check_response
    def get(self):
        """
        Get GCP instance details.

        :return: REST response with operation responsible for the instance
        details retrieval
        """
        self.logger.info('Get instance {0} details'.format(self.name))

        return self.discovery.instances().get(
            instance=self.name,
            project=self.project,
            zone=basename(self.zone)).execute()

    @utils.sync_operation
    @check_response
    def add_access_config(self, ip_address=''):
        """
        Set GCP instance external IP.
        Zone operation.

        :param ip_address: ip address of external IP, if not set new IP
        address assigned
        :return: REST response with operation responsible for the instance
        external IP setting process and its status
        """
        self.logger.info('Add external IP to instance {0}'.format(self.name))

        body = {'kind': 'compute#accessConfig',
                constants.NAME: self.ACCESS_CONFIG,
                'type': self.ACCESS_CONFIG_TYPE}
        if ip_address:
            body['natIP'] = ip_address

        return self.discovery.instances().addAccessConfig(
            project=self.project,
            instance=self.name,
            zone=basename(self.zone),
            networkInterface=self.NETWORK_INTERFACE,
            body=body).execute()

    @utils.sync_operation
    @check_response
    def delete_access_config(self, rule_name=ACCESS_CONFIG,
                             interface=NETWORK_INTERFACE):
        """
        Set GCP instance tags.
        Zone operation.

        :return: REST response with operation responsible for the instance
        external ip removing process and its status
        """
        self.logger.info(
            'Remove external IP from instance {0}'.format(self.name))

        return self.discovery.instances().deleteAccessConfig(
            project=self.project,
            instance=self.name,
            zone=basename(self.zone),
            accessConfig=rule_name,
            networkInterface=interface).execute()

    @utils.sync_operation
    @check_response
    def attach_disk(self, disk):
        """
        Attach disk to the instance.

        :param disk: disk structure to be attached to the instance
        :return:
        """
        return self.discovery.instances().attachDisk(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name,
            body=disk).execute()

    @utils.sync_operation
    @check_response
    def detach_disk(self, disk_name):
        """
        Detach disk identified by the name from the instance.

        :param disk_name: name of the disk to be detached
        :return:
        """
        return self.discovery.instances().detachDisk(
            project=self.project,
            zone=basename(self.zone),
            instance=self.name,
            deviceName=disk_name).execute()

    @check_response
    def list(self):
        """
        List GCP instances.
        Zone operation.

        :return: REST response with a list of instances and its details
        """
        self.logger.info('List instances in project {0}'.format(self.project))

        return self.discovery.instances().list(
            project=self.project,
            zone=basename(self.zone)).execute()

    def to_dict(self):
        def add_key_value_to_metadata(key, value, body):
            ctx.logger.info('Adding {} to metadata'.format(key))
            body['metadata']['items'].append({'key': key, 'value': value})

        network = {'network': 'global/networks/default'}
        if self.network and self.network != 'default':
            network['network'] = self.network
        if self.subnetwork:
            network['subnetwork'] = self.subnetwork

        body = {
            constants.NAME: self.name,
            'description': 'Cloudify generated instance',
            'canIpForward': self.can_ip_forward,
            'tags': {'items': list(set(self.tags))},
            'machineType': 'zones/{0}/machineTypes/{1}'.format(
                basename(self.zone),
                self.machine_type),
            'networkInterfaces': [network],
            'serviceAccounts': [
                {'email': 'default',
                 'scopes': self.scopes
                 }],
        }
        self.body.update(body)
        self.body.setdefault('metadata', {}).setdefault('items', [])
        add_key_value_to_metadata('bucket',
                                  self.project,
                                  self.body)
        ssh_keys_str = '\n'.join(self.ssh_keys)
        add_key_value_to_metadata(KeyPair.KEY_VALUE,
                                  ssh_keys_str,
                                  self.body)
        if self.startup_script.get('value'):
            key = self.startup_script['key']
            value = self.startup_script['value']
            add_key_value_to_metadata(key,
                                      value,
                                      self.body)

        if not self.disks:
            self.disks = [{'boot': True,
                           'autoDelete': True,
                           'initializeParams': {
                               'sourceImage': self.image
                           }}]
        self.body['disks'] = self.disks

        if self.externalIP:
            # GCP Instances only support a single networkInterface, with a
            # single accessConfig, so there's no need to look them up in a
            # sophisiticated way.
            self.body['networkInterfaces'][0]['accessConfigs'] = [{
                'type': self.ACCESS_CONFIG_TYPE,
                constants.NAME: self.ACCESS_CONFIG,
                }]

        ctx.logger.debug('Body that being used: {0}'.format(self.body))
        return self.body


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def create(instance_type,
           image_id,
           name,
           external_ip,
           startup_script,
           scopes,
           tags,
           zone=None,
           can_ip_forward=False,
           additional_settings=None,
           **kwargs):
    if utils.resource_created(ctx, constants.RESOURCE_ID):
        return

    props = ctx.instance.runtime_properties
    gcp_config = utils.get_gcp_config()

    script = _get_script(startup_script)
    ctx.logger.info('The script is {0}'.format(str(startup_script)))

    ssh_keys = get_ssh_keys()

    network, subnetwork = utils.get_net_and_subnet(ctx)

    if zone:
        zone = props['zone'] = utils.get_gcp_resource_name(zone)
    else:
        zone = props.setdefault(
                'zone',
                utils.get_gcp_resource_name(gcp_config['zone']))

    disks = [
            disk.target.instance.runtime_properties[constants.DISK]
            for disk
            in utils.get_relationships(
                ctx,
                filter_resource_types='compute#disk'
                )
            ]
    # There must be exactly one boot disk and that disk must be first in the
    # `disks` list.
    disks.sort(key=lambda disk: disk['boot'], reverse=True)
    boot_disks = [x for x in disks if x['boot']]
    if len(boot_disks) > 1:
        raise NonRecoverableError(
                'Only one disk per Instance may be a boot disk. '
                'Disks: {}'.format(boot_disks)
                )

    instance_name = utils.get_final_resource_name(name)
    instance = Instance(
            gcp_config,
            ctx.logger,
            name=instance_name,
            disks=disks,
            image=image_id,
            machine_type=instance_type,
            external_ip=external_ip,
            startup_script=script,
            scopes=scopes,
            tags=tags,
            ssh_keys=ssh_keys,
            network=network,
            subnetwork=subnetwork,
            zone=zone,
            can_ip_forward=can_ip_forward,
            additional_settings=additional_settings,
            )

    ctx.instance.runtime_properties[constants.RESOURCE_ID] = instance.name
    ctx.instance.runtime_properties[constants.NAME] = instance.name
    ctx.instance.runtime_properties[constants.MACHINE_TYPE] = \
        instance.machine_type
    utils.create(instance)


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def start(name, **kwargs):
    ctx.logger.info('Start operation')
    gcp_config = utils.get_gcp_config()
    props = ctx.instance.runtime_properties

    if not name:
        name = props.get(constants.NAME)

    if name:
        instance = Instance(gcp_config,
                            ctx.logger,
                            name=name,
                            zone=basename(props['zone']),
                            )

        utils.resource_started(ctx, instance)
        set_ip(instance)

        instance.start()


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def delete(name, zone, **kwargs):
    gcp_config = utils.get_gcp_config()
    props = ctx.instance.runtime_properties

    if not zone:
        zone = props.get('zone')
    if not name:
        name = props.get(constants.NAME)

    if name:
        instance = Instance(gcp_config,
                            ctx.logger,
                            name=name,
                            zone=zone,
                            )
        utils.delete_if_not_external(instance)


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def stop(name, zone, **kwargs):
    ctx.logger.info('Stop operation')
    gcp_config = utils.get_gcp_config()
    props = ctx.instance.runtime_properties

    if not zone:
        zone = props.get('zone')
    if not name:
        name = props.get(constants.NAME)

    if name:
        instance = Instance(gcp_config,
                            ctx.logger,
                            name=name,
                            zone=zone,
                            )
        instance.stop()


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def resize(name, zone, machine_type, **kwargs):
    ctx.logger.info('Resize operation')
    gcp_config = utils.get_gcp_config()
    props = ctx.instance.runtime_properties

    if not zone:
        zone = props.get('zone')
    if not name:
        name = props.get(constants.NAME)

    if name:
        instance = Instance(gcp_config,
                            ctx.logger,
                            name=name,
                            zone=zone,
                            )
        instance.stop()
        instance.set_machine_type(name, zone, machine_type)
        instance.start()
        ctx.instance.runtime_properties[constants.MACHINE_TYPE] = machine_type
        instance.machine_type = machine_type


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def add_instance_tag(instance_name, zone, tag, **kwargs):
    config = utils.get_gcp_config()
    config['network'] = utils.get_gcp_resource_name(config['network'])
    instance = Instance(config,
                        ctx.logger,
                        name=instance_name,
                        zone=zone,
                        )
    instance.set_tags([utils.get_gcp_resource_name(t) for t in tag])


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def remove_instance_tag(instance_name, zone, tag, **kwargs):
    config = utils.get_gcp_config()
    if instance_name:
        config['network'] = utils.get_gcp_resource_name(config['network'])
        instance = Instance(config,
                            ctx.logger,
                            name=instance_name,
                            zone=zone,
                            )
        instance.remove_tags([utils.get_gcp_resource_name(t) for t in tag])


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def add_external_ip(instance_name, zone, **kwargs):
    gcp_config = utils.get_gcp_config()
    # check if the instance has no external ips, only one is supported so far
    gcp_config['network'] = utils.get_gcp_resource_name(gcp_config['network'])
    ip_node = ctx.target.node

    # Might be overridden by either `use_external_resource` or a connected
    # Address
    ip_address = ''

    instance = Instance(
            gcp_config,
            ctx.logger,
            name=instance_name,
            zone=zone,
            )

    if utils.should_use_external_resource(ctx.target):
        ip_address = ip_node.properties.get('ip_address') or \
                     ctx.target.instance.runtime_properties.get(constants.IP)
        if not ip_address:
            raise GCPError('{} is set, but ip_address is not set'
                           .format(constants.USE_EXTERNAL_RESOURCE))
    elif ip_node.type == 'cloudify.gcp.nodes.Address':
        ip_address = ctx.target.instance.runtime_properties['address']
    elif ip_node.type != 'cloudify.gcp.nodes.ExternalIP':
        raise NonRecoverableError(
                'Incorrect node type ({}) used as Instance external IP'.format(
                    ip_node.type,
                    ))

    # If `ip_address` is still '' when we get here then the connected IP node
    # must be an ExternalIP, which means we should add the accessConfig
    # *without* a specified IP. The API will produce one for us in this case.

    instance.add_access_config(ip_address)
    set_ip(instance, relationship=True)


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def add_ssh_key(**kwargs):
    key = ctx.target.instance.runtime_properties[constants.PUBLIC_KEY]
    user = ctx.target.instance.runtime_properties[constants.USER]
    key_user_string = utils.get_key_user_string(user, key)
    properties = ctx.source.instance.runtime_properties

    instance_keys = properties.get(constants.SSH_KEYS, [])
    instance_keys.append(key_user_string)
    properties[constants.SSH_KEYS] = instance_keys
    ctx.logger.info('Adding key: {0}'.format(key_user_string))


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def remove_external_ip(instance_name, zone, **kwargs):
    if instance_name:
        gcp_config = utils.get_gcp_config()
        gcp_config['network'] = utils.get_gcp_resource_name(
                gcp_config['network'])
        instance = Instance(gcp_config,
                            ctx.logger,
                            name=instance_name,
                            zone=zone,
                            )
        instance.delete_access_config()


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def attach_disk(instance_name, zone, disk, **kwargs):
    gcp_config = utils.get_gcp_config()
    instance = Instance(gcp_config,
                        ctx.logger,
                        name=instance_name,
                        zone=zone,
                        )
    instance.attach_disk(disk)


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def detach_disk(instance_name, zone, disk_name, **kwargs):
    gcp_config = utils.get_gcp_config()
    instance = Instance(gcp_config,
                        ctx.logger,
                        name=instance_name,
                        zone=zone,
                        )
    instance.detach_disk(disk_name)


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def contained_in(**kwargs):
    key = ctx.target.instance.runtime_properties[constants.SSH_KEYS]
    ctx.source.instance.runtime_properties[constants.SSH_KEYS] = key
    ctx.logger.info('Copied ssh keys to the node')


def set_ip(instance, relationship=False):
    if relationship:
        props = ctx.source.instance.runtime_properties
    else:
        props = ctx.instance.runtime_properties

    instances = instance.list()
    item = utils.get_item_from_gcp_response(constants.NAME,
                                            instance.name,
                                            instances)

    try:
        props['ip'] = item['networkInterfaces'][0]['networkIP']
        if relationship or ctx.node.properties['external_ip']:
            public = item['networkInterfaces'][0]['accessConfigs'][0]['natIP']
            props['public_ip_address'] = public
            # Check to see if "use_public_ip" is enabled or not
            if ctx.node.properties.get('use_public_ip'):
                props['ip'] = public
    except (TypeError, KeyError):
        ctx.operation.retry(
                'The instance has not yet created network interface', 10)
    props.update(item)


def get_ssh_keys():
    instance_keys = ctx.instance.runtime_properties.get(constants.SSH_KEYS, [])
    install = ctx.node.properties['install_agent']
    # properties['install_agent'] defaults to '', but that means true!
    agent_config = ctx.node.properties.get('agent_config', {})
    if not any([
            agent_config.get('install_method') == 'none',
            install is False,
            ]):
        agent_key = utils.get_agent_ssh_key_string()
        instance_keys.append(agent_key)
    return list(set(instance_keys))


def validate_contained_in_network(**kwargs):
    rels = utils.get_relationships(
            ctx,
            filter_relationships='cloudify.gcp.relationships.'
                                 'instance_contained_in_network',
            filter_resource_types=[
                'cloudify.nodes.gcp.Network',
                'cloudify.nodes.gcp.SubNetwork',
                'cloudify.gcp.nodes.Network',
                'cloudify.gcp.nodes.SubNetwork',
                ],
            )
    if len(rels) > 1:
        raise NonRecoverableError(
                'Instances may only be contained in 1 Network or SubNetwork')
    elif len(rels) == 1:
        network = rels[0].target
        if network.node.type == 'cloudify.nodes.gcp.Network' or \
                network.node.type == 'cloudify.gcp.nodes.Network' and \
                not network.node.properties['auto_subnets']:
            raise NonRecoverableError(
                    'It is invalid to connect an instance directly to a '
                    'network with custom Subtneworks (i.e. `auto_subnets` '
                    'disabled')


def _get_script(startup_script):
    """In plugin versions 1.0.0-1.0.1, startup-script was a either a string or
    a dict. The dict would have the keys type and script. 1.1.0 Introduces a
    structure that is more consistent with the GCP API. This method supports
    both.
    """

    if hasattr(startup_script, 'get'):
        startup_script_metadata = {
            'key': startup_script.get('key', 'startup-script')
        }
        if startup_script.get('type') == 'file':
            startup_script_metadata['value'] = \
                ctx.get_resource(startup_script.get('script'))
        elif startup_script.get('type') == 'string':
            startup_script_metadata['value'] = startup_script.get('script')
        else:
            startup_script_metadata['value'] = startup_script.get('value')
    else:
        startup_script_metadata = {
            'key': 'startup-script',
            'value': startup_script if isinstance(startup_script,
                                                  _compat.text_type) else ''
        }

    install_agent_script = ctx.agent.init_script()
    os_family = ctx.node.properties['os_family']

    if install_agent_script:
        existing_startup_script_value = startup_script_metadata['value']
        if startup_script_metadata.get('key') in POWERSHELL_SCRIPTS and \
                os_family == 'windows':
            split_agent_script = re.split('{0}|{1}'.format(PS_OPEN, PS_CLOSE),
                                          install_agent_script)
            split_agent_script.insert(0, existing_startup_script_value)
            split_agent_script.insert(0, PS_OPEN)
            split_agent_script.insert(len(split_agent_script), PS_CLOSE)
        else:
            split_agent_script = [existing_startup_script_value,
                                  install_agent_script]
        new_startup_script_value = '\n'.join(split_agent_script)
        startup_script_metadata['value'] = new_startup_script_value

    return startup_script_metadata


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def instance_remove_access_config(instance_name, zone, rule_name, interface,
                                  **kwargs):
    # config from source
    gcp_config = utils.get_gcp_config()

    instance = Instance(gcp_config,
                        ctx.logger,
                        name=instance_name,
                        zone=zone,
                        )
    instance.delete_access_config(rule_name, interface)
