#!/usr/bin/env python3

import unittest
import amulet


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
        cls.d.relate('kafka:zookeeper', 'zookeeper:zookeeper')

        cls.d.setup(timeout=900)
        cls.d.sentry.wait(timeout=1800)
        cls.unit = cls.d.sentry['kafka'][0]

    def test_deploy(self):
        output, retcode = self.unit.run("pgrep -a java")
        assert 'Kafka' in output, "Kafka daemon is not started"


if __name__ == '__main__':
    unittest.main()
