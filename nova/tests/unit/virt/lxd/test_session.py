# Copyright 2015 Canonical Ltd
# All Rights Reserved.
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
#    implied. See the License for the specific language governing
#    permissions and limitations under the License.

"""
Unit tests for ContinerMixin class

The following tests the ContainerMixin class
for nova-lxd.
"""

import ddt
import mock

from nova import exception
from nova import test
from pylxd.deprecated import exceptions as lxd_exceptions

from nova.virt.lxd import session
import fake_api
import stubs


@ddt.ddt
class SessionContainerTest(test.NoDBTestCase):

    def setUp(self):
        super(SessionContainerTest, self).setUp()

        """This is so we can mock out pylxd API calls."""
        self.ml = stubs.lxd_mock()
        lxd_patcher = mock.patch('pylxd.deprecated.api.API',
                                 mock.Mock(return_value=self.ml))
        lxd_patcher.start()
        self.addCleanup(lxd_patcher.stop)

        self.session = session.LXDAPISession()

    @stubs.annotated_data(
        ('exists', True),
        ('missing', False),
    )
    def test_container_defined(self, tag, side_effect):
        """
        container_defined returns True if the container
        exists on an LXD host, False otherwise, verify
        the apporiate return value is returned.
        """
        instance = stubs._fake_instance()
        self.ml.container_defined.return_value = side_effect
        if side_effect:
            self.assertTrue(self.session.container_defined(
                instance.name, instance))
        if not side_effect:
            self.assertFalse(self.session.container_defined(
                instance.name, instance))

    @stubs.annotated_data(
        ('1', True, (200, fake_api.fake_operation_info_ok()))
    )
    def test_container_start(self, tag, defined, side_effect=None):
        """
        containser_start starts a container on a given LXD host.
        Verify that the correct pyLXD calls are made.
        """
        instance = stubs._fake_instance()
        self.ml.container_start.return_value = side_effect
        self.assertEqual(None,
                         self.session.container_start(instance.name,
                                                      instance))
        calls = [mock.call.container_start(instance.name, -1),
                 mock.call.wait_container_operation(
            '/1.0/operation/1234', 200, -1)]
        self.assertEqual(calls, self.ml.method_calls)

    @stubs.annotated_data(
        ('exists', (200, fake_api.fake_operation_info_ok())),
    )
    def test_container_destroy(self, tag, side_effect):
        """
        container_destroy delete a container from the LXD Host. Check
        that the approiate pylxd calls are made.
        """
        instance = stubs._fake_instance()
        self.ml.container_stop.return_value = side_effect
        self.ml.container_destroy.return_value = side_effect
        self.assertEqual(None,
                         self.session.container_destroy(instance.name,
                                                        instance))
        calls = [mock.call.container_stop(instance.name, -1),
                 mock.call.wait_container_operation(
            '/1.0/operation/1234', 200, -1),
            mock.call.container_destroy(instance.name),
            mock.call.wait_container_operation(
            '/1.0/operation/1234', 200, -1)]
        self.assertEqual(calls, self.ml.method_calls)

    @stubs.annotated_data(
        ('fail_to_stop', True, 'fail_stop',
         lxd_exceptions.APIError('Fake', '500'), exception.NovaException),
        ('fail_to_destroy', True, 'fail_destroy',
         lxd_exceptions.APIError('Fake', '500'), exception.NovaException)
    )
    def test_container_destroy_fail(self, tag, container_defined,
                                    test_type, side_effect, expected):
        """
        container_destroy deletes a container on the LXD host.
        Check whether an exeption.NovaException is raised when
        there is an APIError or when the container fails to stop.
        """
        instance = stubs._fake_instance()
        self.ml.cotnainer_defined.return_value = container_defined
        if test_type == 'fail_stop':
            self.ml.container_stop.side_effect = side_effect
            self.assertRaises(expected,
                              self.session.container_destroy, instance.name,
                              instance)
        if test_type == 'fail_destroy':
            self.ml.container_stop.return_value = \
                (200, fake_api.fake_operation_info_ok())
            self.ml.container_destroy.side_effect = side_effect
            self.assertRaises(expected,
                              self.session.container_destroy, instance.name,
                              instance)

    @stubs.annotated_data(
        ('1', (200, fake_api.fake_operation_info_ok()))
    )
    def test_container_init(self, tag, side_effect):
        """
        conatainer_init creates a container based on given config
        for a container. Check to see if we are returning the right
        pylxd calls for the LXD API.
        """
        config = mock.Mock()
        instance = stubs._fake_instance()
        self.ml.container_init.return_value = side_effect
        self.ml.operation_info.return_value = \
            (200, fake_api.fake_container_state(200))
        self.assertEqual(None,
                         self.session.container_init(config, instance))
        calls = [mock.call.container_init(config),
                 mock.call.wait_container_operation(
                     '/1.0/operation/1234', 200, -1),
                 mock.call.operation_info('/1.0/operation/1234')]
        self.assertEqual(calls, self.ml.method_calls)

    @stubs.annotated_data(
        ('api_fail', lxd_exceptions.APIError(500, 'Fake'),
         exception.NovaException),
    )
    def test_container_init_fail(self, tag, side_effect, expected):
        """
        continer_init create as container on a given LXD host. Make
        sure that we reaise an exception.NovaException if there is
        an APIError from the LXD API.
        """
        config = mock.Mock()
        instance = stubs._fake_instance()
        self.ml.container_init.side_effect = side_effect
        self.assertRaises(expected,
                          self.session.container_init, config,
                          instance)


@ddt.ddt
class SessionEventTest(test.NoDBTestCase):

    def setUp(self):
        super(SessionEventTest, self).setUp()

        self.ml = stubs.lxd_mock()
        lxd_patcher = mock.patch('pylxd.deprecated.api.API',
                                 mock.Mock(return_value=self.ml))
        lxd_patcher.start()
        self.addCleanup(lxd_patcher.stop)

        self.session = session.LXDAPISession()

    def test_container_wait(self):
        instance = stubs._fake_instance()
        operation_id = mock.Mock()
        self.ml.wait_container_operation.return_value = True
        self.assertEqual(None,
                         self.session.operation_wait(operation_id, instance))
        self.ml.wait_container_operation.assert_called_with(operation_id,
                                                            200, -1)


@ddt.ddt
class SessionImageTest(test.NoDBTestCase):

    def setUp(self):
        super(SessionImageTest, self).setUp()

        self.ml = stubs.lxd_mock()
        lxd_patcher = mock.patch('pylxd.deprecated.api.API',
                                 mock.Mock(return_value=self.ml))
        lxd_patcher.start()
        self.addCleanup(lxd_patcher.stop)

        self.session = session.LXDAPISession()

    def test_image_defined(self):
        """Test the image is defined in the LXD hypervisor."""
        instance = stubs._fake_instance()
        self.ml.alias_defined.return_value = True
        self.assertTrue(self.session.image_defined(instance))
        calls = [mock.call.alias_defined(instance.image_ref)]
        self.assertEqual(calls, self.ml.method_calls)

    def test_alias_create(self):
        """Test the alias is created."""
        instance = stubs._fake_instance()
        alias = mock.Mock()
        self.ml.alias_create.return_value = True
        self.assertTrue(self.session.create_alias(alias, instance))
        calls = [mock.call.alias_create(alias)]
        self.assertEqual(calls, self.ml.method_calls)


@ddt.ddt
class SessionProfileTest(test.NoDBTestCase):

    def setUp(self):
        super(SessionProfileTest, self).setUp()

        """This is so we can mock out pylxd API calls."""
        self.ml = stubs.lxd_mock()
        lxd_patcher = mock.patch('pylxd.deprecated.api.API',
                                 mock.Mock(return_value=self.ml))
        lxd_patcher.start()
        self.addCleanup(lxd_patcher.stop)

        self.session = session.LXDAPISession()

    @stubs.annotated_data(
        ('empty', [], []),
        ('valid', ['test'], ['test']),
    )
    def test_profile_list(self, tag, side_effect, expected):
        self.ml.profile_list.return_value = side_effect
        self.assertEqual(expected,
                         self.session.profile_list())

    def test_profile_list_fail(self):
        self.ml.profile_list.side_effect = (
            lxd_exceptions.APIError('Fake', 500))
        self.assertRaises(
            exception.NovaException,
            self.session.profile_list)

    def test_profile_create(self):
        instance = stubs._fake_instance()
        config = mock.Mock()
        self.ml.profile_defined.return_value = True
        self.ml.profile_create.return_value = \
            (200, fake_api.fake_standard_return())
        self.assertEqual((200, fake_api.fake_standard_return()),
                         self.session.profile_create(config,
                                                     instance))
        calls = [mock.call.profile_list(),
                 mock.call.profile_create(config)]
        self.assertEqual(calls, self.ml.method_calls)

    def test_profile_delete(self):
        instance = stubs._fake_instance()
        self.ml.profile_defined.return_value = True
        self.ml.profile_delete.return_value = \
            (200, fake_api.fake_standard_return())
        self.assertEqual(None,
                         self.session.profile_delete(instance))
