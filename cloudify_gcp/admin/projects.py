# #######
# Copyright (c) 2018-2020 Cloudify Platform Ltd. All rights reserved
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

from cloudify import ctx
from cloudify.decorators import operation

from .. import gcp
from .. import utils
from .. import constants
from . import CloudResourcesBase


class Project(CloudResourcesBase):

    def __init__(self, config, logger, project_id=None, name=None):
        super(CloudResourcesBase, self).__init__(config, logger)
        self.project_id = utils.get_gcp_resource_name(project_id)
        self.name = name if name else self.project_id

    @gcp.check_response
    def get(self):
        """
        Get GCP project details.

        :return: REST response with operation responsible for the project
        details retrieval
        """
        self.logger.info('Get instance {0} details'.format(self.name))

        return self.discovery.projects().get(
            projectId=self.project_id).execute()

    @gcp.check_response
    def create(self):
        project_body = {
            constants.NAME: utils.get_gcp_resource_name(
                ctx.node.properties[constants.NAME]),
            'projectId': self.project_id
        }
        self.logger.info('Project info: {}'.format(repr(project_body)))
        return self.discovery.projects().create(
            body=project_body).execute()

    @gcp.check_response
    def delete(self):
        return self.discovery.projects().delete(
            projectId=self.project_id).execute()


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def create(**_):
    if utils.resource_created(ctx, constants.RESOURCE_ID):
        return

    gcp_config = utils.get_gcp_config()

    project = Project(
        gcp_config,
        ctx.logger,
        ctx.node.properties['id'],
        ctx.node.properties[constants.NAME]
    )
    utils.create(project)

    ctx.instance.runtime_properties[constants.RESOURCE_ID] = project.project_id


@operation(resumable=True)
@utils.throw_cloudify_exceptions
def delete(**_):
    gcp_config = utils.get_gcp_config()
    props = ctx.instance.runtime_properties

    if props.get(constants.RESOURCE_ID):
        project = Project(
            gcp_config,
            ctx.logger,
            props[constants.RESOURCE_ID]
        )

        utils.delete_if_not_external(project)
        ctx.instance.runtime_properties[constants.RESOURCE_ID] = None
