#!/usr/bin/env python3

import unittest
import amulet
import re


class TestDeploy(unittest.TestCase):
    """
    Trivial deployment test for Apache Kafka.

    This charm cannot do anything useful by itself, so integration testing
    is done in the bundle.
    """

    @classmethod
    def setUpClass(cls):
        cls.d = amulet.Deployment(series='trusty')
        cls.d.add('kafka', 'apache-kafka')
        cls.d.add('zookeeper', 'apache-zookeeper')
        cls.d.relate('kafka:zookeeper', 'zookeeper:zkclient')

        cls.d.setup(timeout=900)
        cls.d.sentry.wait(timeout=1800)
        cls.unit = cls.d.sentry['kafka'][0]

    def test_deploy(self):
        output, retcode = self.unit.run("pgrep -a java")
        assert 'Kafka' in output, "Kafka daemon is not started"

    def test_bind_network_interface(self):
        '''
        Test to verify that we can bind to a specific network interface.

        '''
        self.d.log.debug("Binding Kafka to eth0")
        self.d.configure('kafka', {'network_interface': 'eth0'})
        self.d.sentry.wait_for_messages({'kafka': 'Server config changed: restarting Kafka'}, timeout=60)
        self.d.sentry.wait_for_messages({'kafka': 'Ready'}, timeout=600)

        self.d.log.debug("Checking kafka bindings ...")
        ret = self.unit.run(
            'grep host.name /etc/kafka/conf/server.properties')[0]
        # Correct line should start with host.name (no comment hash
        # mark), followed by an equals sign and something that looks
        # like an IP address (we aren't too strict about it being a
        # valid ip address.)
        matcher = re.compile("^host\.name=\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}.*")

        self.assertTrue('host.name' in ret)
        self.assertTrue(matcher.match(ret))

    def test_reset_network_interface(self):
        """
        Verify that we can reset the charm to listen on any network interface.

        """
        self.d.log.debug("Binding Kafka to 0.0.0.0")
        self.d.configure('kafka', {'network_interface': '0.0.0.0'})
        self.d.sentry.wait_for_messages({'kafka': 'Server config changed: restarting Kafka'}, timeout=60)
        self.d.sentry.wait_for_messages({'kafka': 'Ready'}, timeout=600)

        self.d.log.debug("Checking reset bindings ...")
        ret = self.unit.run(
            'grep host.name /etc/kafka/conf/server.properties')[0]

        matcher = re.compile("^host\.name=0\.0\.0\.0.*")
        self.assertTrue(matcher.match(ret))


if __name__ == '__main__':
    unittest.main()
