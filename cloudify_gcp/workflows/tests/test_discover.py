from unittest import TestCase
from mock import patch, call, MagicMock

from ..._compat import PY2
from .. import resources, discover


@patch('cloudify_gcp.gcp.ServiceAccountCredentials.from_json_keyfile_dict')
@patch('cloudify_gcp.utils.get_gcp_resource_name', return_value='valid_name')
@patch('cloudify_gcp.gcp.build')
class GCPeWorkflowTests(TestCase):

    def get_mock_rest_client(self):
        mock_node = MagicMock(node_id='foo',
                              type_hierarchy=discover.GCP_TYPE)
        mock_node.id = mock_node.node_id
        mock_node.properties = {
            'client_config': {},
            'resource_config': {},
            'zones': []
        }
        nodes_list = [mock_node]
        mock_nodes_client = MagicMock()
        mock_nodes_client.list = MagicMock(return_value=nodes_list)
        mock_instance = MagicMock(node_id='foo', state='started')
        mock_instance.node = mock_node
        mock_instance.node_id = mock_node.node_id
        mock_instance.runtime_properties = {}
        instances_list = [mock_instance]
        mock_instances_client = MagicMock()
        mock_instances_client.list = MagicMock(return_value=instances_list)
        mock_deployments_client = MagicMock()
        mock_deployments_client.create = MagicMock()
        mock_deployments_client.get.return_value = None
        mock_deployment_groups_client = MagicMock()
        mock_deployment_groups_client.put = MagicMock()
        mock_rest_client = MagicMock()
        mock_rest_client.nodes = mock_nodes_client
        mock_rest_client.node_instances = mock_instances_client
        mock_rest_client.deployments = mock_deployments_client
        mock_rest_client.deployment_groups = mock_deployment_groups_client
        return mock_rest_client

    @patch('cloudify_gcp.workflows.discover.get_resources')
    def test_discover_resources(self, mock_get_resources, *_):
        mock_ctx = MagicMock()
        node = MagicMock()
        node_instance = MagicMock()
        node_instance._node_instance = MagicMock(
            runtime_properties={'resources': {}})
        result = {'foo': 'bar'}
        mock_get_resources.return_value = result
        node_instances = [node_instance]
        node.instances = node_instances
        mock_ctx.get_node.return_value = node
        params = {
            'node_id': 'foo',
            'resource_types': ['bar', 'baz'],
            'zones': ['taco'],
            'ctx': mock_ctx
        }
        self.assertEqual(discover.discover_resources(**params), result)

    @patch('cloudify_common_sdk.utils.get_rest_client')
    def test_deploy_resources(self, get_rest_client, *_):
        mock_rest_client = self.get_mock_rest_client()
        get_rest_client.return_value = mock_rest_client
        mock_ctx = MagicMock()
        params = {
            'group_id': 'foo',
            'blueprint_id': 'bar',
            'deployment_ids': ['taco'],
            'inputs': [{'winter': 'not fun'}],
            'labels': [{'beach': 'fun'}],
            'ctx': mock_ctx
        }
        discover.deploy_resources(**params)
        self.assertTrue(
            mock_rest_client.deployment_groups.put.called)
        self.assertTrue(
            mock_rest_client.deployment_groups.add_deployments.called)

    @patch('cloudify_common_sdk.utils.get_rest_client')
    @patch('cloudify_gcp.workflows.discover.deploy_resources')
    @patch('cloudify_gcp.workflows.discover.discover_resources')
    def test_discover_and_deploy(self, mock_discover, mock_deploy, *_):
        mock_ctx = MagicMock()
        mock_ctx.deployment = MagicMock(id='foo')
        mock_ctx.blueprint = MagicMock(id='bar')
        params = {
            'node_id': 'foo',
            'resource_types': ['bar', 'baz'],
            'zones': ['taco'],
            'blueprint_id': 'foo',
            'ctx': mock_ctx
        }
        mock_discover.return_value = {
            'region1': {
                'resource_type1': {
                    'resource1': MagicMock(),
                    'resource2': MagicMock(),
                },
                'resource_type2': {
                    'resource3': MagicMock()
                },
            },
            'region2': {
                'resource_type1': {
                    'resource4': MagicMock()
                }
            }
        }
        discover.discover_and_deploy(**params)
        self.assertEqual(mock_deploy.call_count, 3)
        expected_calls = [
            call('foo', 'foo', ['foo-resource1', 'foo-resource2'],
                 [{'kubernetes_cluster_name': 'resource1',
                   'zone': 'region1'},
                  {'kubernetes_cluster_name': 'resource2',
                   'zone': 'region1'}],
                 [{'csys-env-type': 'environment'},
                  {'csys-obj-parent': 'foo'}],
                 mock_ctx),
            call('foo', 'foo', ['foo-resource3'], [
                {'kubernetes_cluster_name': 'resource3', 'zone': 'region1'}],
                 [{'csys-env-type': 'environment'},
                  {'csys-obj-parent': 'foo'}],
                 mock_ctx),
            call('foo', 'foo', ['foo-resource4'],
                 [{'kubernetes_cluster_name': 'resource4',
                   'zone': 'region2'}],
                 [{'csys-env-type': 'environment'},
                  {'csys-obj-parent': 'foo'}],
                 mock_ctx)]
        if PY2:
            return
        mock_deploy.assert_has_calls(expected_calls)

    @patch('cloudify_gcp.container_engine.cluster')
    def test_get_resources(self, *_):
        mock_ctx = MagicMock()
        node = MagicMock(
            properties={
                'client_config': {
                    'auth': {'foo': 'bar'},
                    'project': 'foo',
                    'zone': 'bar'
                }
            }
        )
        node_instance = MagicMock()
        node_instance._node_instance = MagicMock(
            runtime_properties={'resources': {}})
        node_instances = [node_instance]
        node.instances = node_instances
        mock_ctx.get_node.return_value = node
        mock_ctx.logger = MagicMock()
        params = {
            'node': node,
            'zones': ['region1', 'region2'],
            'resource_types': ['projects.zones.clusters'],
            'logger': mock_ctx.logger
        }
        self.assertEqual(resources.get_resources(**params), {})

    @patch('cloudify_gcp.container_engine.cluster.Cluster.list')
    def test_initialize(self, *_):
        mock_ctx = MagicMock()
        mock_ctx.node = MagicMock(
            properties={
                'client_config': {
                    'auth': {'foo': 'bar'},
                    'project': 'foo',
                    'zone': 'bar'
                }
            }
        )
        mock_ctx.instance = MagicMock(runtime_properties={'resources': {}})
        params = {
            'resource_config': {'resource_types': [
                'projects.zones.clusters']},
            'zones': ['region1', 'region2'],
            'ctx': mock_ctx,
            'logger': mock_ctx.logger
        }
        resources.initialize(**params)
        self.assertIn('resources',
                      mock_ctx.instance.runtime_properties)
