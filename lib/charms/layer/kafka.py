import os

import jujuresources
from charmhelpers.core import hookenv, templating, host
from jujubigdata import utils


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

        # Configure immutable bits
        kafka_bin = self.dist_config.path('kafka') / 'bin'
        with utils.environment_edit_in_place('/etc/environment') as env:
            if kafka_bin not in env['PATH']:
                env['PATH'] = ':'.join([env['PATH'], kafka_bin])
            env['LOG_DIR'] = self.dist_config.path('kafka_app_logs')

        # note: we set the advertised.host.name below to the public_address
        # to ensure that external (non-Juju) clients can connect to Kafka
        public_address = hookenv.unit_get('public-address')
        private_ip = utils.resolve_private_address(hookenv.unit_get('private-address'))
        kafka_server_conf = self.dist_config.path('kafka_conf') / 'server.properties'
        service, unit_num = os.environ['JUJU_UNIT_NAME'].split('/', 1)
        utils.re_edit_in_place(kafka_server_conf, {
            r'^broker.id=.*': 'broker.id=%s' % unit_num,
            r'^port=.*': 'port=%s' % self.dist_config.port('kafka'),
            r'^log.dirs=.*': 'log.dirs=%s' % self.dist_config.path('kafka_data_logs'),
            r'^#?advertised.host.name=.*': 'advertised.host.name=%s' % public_address,
        })

        kafka_log4j = self.dist_config.path('kafka_conf') / 'log4j.properties'
        utils.re_edit_in_place(kafka_log4j, {
            r'^kafka.logs.dir=.*': 'kafka.logs.dir=%s' % self.dist_config.path('kafka_app_logs'),
        })

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

        # fix for lxc containers and some corner cases in manual provider
        # ensure that public_address is resolvable internally by mapping it to the private IP
        utils.update_kv_host(private_ip, public_address)
        utils.manage_etc_hosts()

    def open_ports(self):
        for port in self.dist_config.exposed_ports('kafka'):
            hookenv.open_port(port)

    def configure_kafka(self, zk_units):
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
