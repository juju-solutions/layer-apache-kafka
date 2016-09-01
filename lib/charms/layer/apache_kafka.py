import os

import jujuresources
import ipaddress
import netifaces
from charmhelpers.core import hookenv, templating, host
from jujubigdata import utils
from subprocess import check_output


class KafkaException(Exception):
    '''
    Exception to raise in the case where we run into trouble
    configuring or running Kafka.

    '''


class Kafka(object):
    def __init__(self, dist_config=None):
        self.dist_config = dist_config or utils.DistConfig()
        self.resources = {
            'kafka': 'kafka-%s' % utils.cpu_arch(),
        }
        self.verify_resources = utils.verify_resources(*self.resources.values())

    def install(self):
        self.dist_config.add_users()
        self.dist_config.add_dirs()
        jujuresources.install(self.resources['kafka'],
                              destination=self.dist_config.path('kafka'),
                              skip_top_level=True)
        self.setup_kafka_config()

    def setup_kafka_config(self):
        '''
        copy the default configuration files to kafka_conf property
        defined in dist.yaml
        '''
        default_conf = self.dist_config.path('kafka') / 'config'
        kafka_conf = self.dist_config.path('kafka_conf')
        kafka_conf.rmtree_p()
        default_conf.copytree(kafka_conf)
        # Now remove the conf included in the tarball and symlink our real conf
        # dir. we've seen issues where kafka still looks for config in
        # KAFKA_HOME/config.
        default_conf.rmtree_p()
        kafka_conf.symlink(default_conf)

        # Similarly, we've seen issues where kafka wants to write to
        # KAFKA_HOME/logs regardless of the LOG_DIR, so make a symlink.
        default_logs = self.dist_config.path('kafka') / 'logs'
        kafka_logs = self.dist_config.path('kafka_app_logs')
        default_logs.rmtree_p()
        kafka_logs.symlink(default_logs)

        # Configure environment
        kafka_bin = self.dist_config.path('kafka') / 'bin'
        with utils.environment_edit_in_place('/etc/environment') as env:
            if kafka_bin not in env['PATH']:
                env['PATH'] = ':'.join([env['PATH'], kafka_bin])
            env['LOG_DIR'] = self.dist_config.path('kafka_app_logs')

        # Configure server.properties
        # NB: We set the advertised.host.name below to our short hostname
        # instead of our private ip so external (non-Juju) clients can connect
        # to kafka (admin will still have to expose kafka and ensure the
        # external client can resolve the short hostname to our public ip).
        short_host = check_output(['hostname', '-s']).decode('utf8').strip()
        kafka_port = self.dist_config.port('kafka')
        kafka_server_conf = self.dist_config.path('kafka_conf') / 'server.properties'
        service, unit_num = os.environ['JUJU_UNIT_NAME'].split('/', 1)
        utils.re_edit_in_place(kafka_server_conf, {
            r'^broker.id=.*': 'broker.id=%s' % unit_num,
            r'^port=.*': 'port=%s' % kafka_port,
            r'^log.dirs=.*': 'log.dirs=%s' % self.dist_config.path('kafka_data_logs'),
            r'^#?advertised.host.name=.*': 'advertised.host.name=%s' % short_host,
        })

        # Configure producer.properties
        # note: we set the broker list to whatever we advertise our broker to
        # be (advertised.host.name from above, which is our short hostname).
        kafka_producer_conf = self.dist_config.path('kafka_conf') / 'producer.properties'
        utils.re_edit_in_place(kafka_producer_conf, {
            r'^#?metadata.broker.list=.*': 'metadata.broker.list=%s:%s' % (short_host, kafka_port),
        })

        # Configure log properties
        kafka_log4j = self.dist_config.path('kafka_conf') / 'log4j.properties'
        utils.re_edit_in_place(kafka_log4j, {
            r'^kafka.logs.dir=.*': 'kafka.logs.dir=%s' % self.dist_config.path('kafka_app_logs'),
        })

        # Configure init script
        template_name = 'upstart.conf'
        template_path = '/etc/init/kafka.conf'
        if host.init_is_systemd():
            template_name = 'systemd.conf'
            template_path = '/etc/systemd/system/kafka.service'

        templating.render(
            template_name,
            template_path,
            context={
                'kafka_conf': self.dist_config.path('kafka_conf'),
                'kafka_bin': '{}/bin'.format(self.dist_config.path('kafka'))
            },
        )

    def open_ports(self):
        for port in self.dist_config.exposed_ports('kafka'):
            hookenv.open_port(port)

    def configure_kafka(self, zk_units, network_interface=None):
        # Get ip:port data from our connected zookeepers
        zks = []
        for unit in zk_units:
            ip = utils.resolve_private_address(unit['host'])
            zks.append("%s:%s" % (ip, unit['port']))
        zks.sort()
        zk_connect = ",".join(zks)

        # update consumer props
        cfg = self.dist_config.path('kafka_conf') / 'consumer.properties'
        utils.re_edit_in_place(cfg, {
            r'^zookeeper.connect=.*': 'zookeeper.connect=%s' % zk_connect,
        })

        # update server props
        cfg = self.dist_config.path('kafka_conf') / 'server.properties'
        utils.re_edit_in_place(cfg, {
            r'^zookeeper.connect=.*': 'zookeeper.connect=%s' % zk_connect,
        })

        # Possibly bind a network interface
        if network_interface:
            utils.re_edit_in_place(cfg, {
                r'^#?host.name=.*': 'host.name={}'.format(
                    self.get_ip_for_interface(network_interface)),
            })

    def restart(self):
        self.stop()
        self.start()

    def start(self):
        host.service_start('kafka')

    def stop(self):
        host.service_stop('kafka')

    def cleanup(self):
        self.dist_config.remove_users()
        self.dist_config.remove_dirs()

    def get_ip_for_interface(self, network_interface):
        """
        Helper to return the ip address of this machine on a specific
        interface.

        @param str network_interface: either the name of the
        interface, or a CIDR range, in which we expect the interface's
        ip to fall. Also accepts 0.0.0.0 (and variants, like 0/0) as a
        special case, which will simply return what you passed in.

        """
        if network_interface.startswith('0') or network_interface == '::':
            # Allow users to reset the charm to listening on any
            # interface.  Allow operators to specify this however they
            # wish (0.0.0.0, ::, 0/0, etc.).
            return network_interface

        # Is this a CIDR range, or an interface name?
        is_cidr = len(network_interface.split(".")) == 4 or len(
            network_interface.split(":")) == 8

        if is_cidr:
            interfaces = netifaces.interfaces()
            for interface in interfaces:
                for ip_version in netifaces.AF_INET, netifaces.AF_INET6:
                    try:
                        ip = netifaces.ifaddresses(
                            interface)[ip_version][0]['addr']
                    except KeyError:
                        continue

                    if ipaddress.ip_address(ip) in ipaddress.ip_network(
                            network_interface):
                        return ip

            raise KafkaException(
                u"This machine has no interfaces in CIDR range {}".format(
                    network_interface))
        else:
            try:
                ip = netifaces.ifaddresses(network_interface)[netifaces.AF_INET][0]['addr']
            except ValueError:
                raise KafkaException(
                    u"This machine does not have an interface '{}'".format(
                        network_interface))
            return ip
