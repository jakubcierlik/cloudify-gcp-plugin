# -*- coding: utf-8 -*-
########
# Copyright (c) 2017-2020 Cloudify Platform Ltd. All rights reserved
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

# Local imports
from __future__ import unicode_literals

# Third-party imports
import mock
from mock import patch

from ...tests import TestGCP
from cloudify_gcp.iam import policy_binding

POLICY_A = {'bindings': [{'foo': 'bar'}]}
POLICY_B = {'bindings': [{'baz': 'taco'}]}
MERGED_POLICY = {'bindings': [{'baz': 'taco'}, {'foo': 'bar'}]}


@patch('cloudify_gcp.utils.assure_resource_id_correct', return_value=True)
@patch('cloudify_gcp.iam.policy_binding._JWTAccessCredentials')
@patch('cloudify_gcp.iam.policy_binding.build')
class TestGCPPolicyBinding(TestGCP):

    def test_create(self, mock_build, *_):
        policy_binding.create(
            resource='foo', policy=POLICY_A)
        mock_build().projects().getIamPolicy.assert_any_call(
            resource='foo', body={'options': {'requestedPolicyVersion': 3}})
        mock_build().projects().setIamPolicy.assert_called_once()

    def test_delete(self, mock_build, *_):
        policy_binding.delete(
            resource='foo', policy=POLICY_A)
        mock_build().projects().getIamPolicy.assert_any_call(
            resource='foo', body={'options': {'requestedPolicyVersion': 3}})
        mock_build().projects().setIamPolicy.assert_called_once()

    @patch('cloudify_gcp.iam.policy_binding.PolicyBinding.get',
           return_value=POLICY_B)
    def test_add_new_policies_to_current_policy(self, *_):
        pb = policy_binding.PolicyBinding(
            mock.MagicMock(),
            mock.MagicMock(),
            'foo',
            POLICY_A
        )
        output = pb.add_new_policies_to_current_policy()
        self.assertEqual(output, MERGED_POLICY)

    @patch('cloudify_gcp.iam.policy_binding.PolicyBinding.get',
           return_value=POLICY_B)
    def test_remove_new_policies_from_current_policy(self, *_):
        pb = policy_binding.PolicyBinding(
            mock.MagicMock(),
            mock.MagicMock(),
            'foo',
            POLICY_A
        )
        output = pb.remove_new_policies_from_current_policy()
        self.assertEqual(output, POLICY_B)
