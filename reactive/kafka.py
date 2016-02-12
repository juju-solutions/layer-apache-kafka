import jujuresources
from charms.reactive import when, when_not
from charms.reactive import set_state, remove_state
from charmhelpers.core import hookenv
from charms.kafka import Kafka
from jujubigdata.utils import DistConfig

def dist_config():

    if not getattr(dist_config, 'value', None):
        kafka_reqs = ['vendor', 'packages', 'groups', 'users', 'dirs', 'ports']
        dist_config.value = DistConfig(filename='dist.yaml', required_keys=kafka_reqs)
    return dist_config.value


@when_not('kafka.installed')
def install_kafka(*args):

    kafka = Kafka(dist_config())
    if kafka.verify_resources():
        hookenv.status_set('maintenance', 'Installing Kafka')
        kafka.install()
        kafka.open_ports()
        set_state('kafka.installed')


@when('kafka.installed')
@when_not('zookeeper.connected')
def waiting_for_zookeeper_connection():
    hookenv.status_set('blocked', 'Waiting for connection to Zookeeper')


@when('kafka.installed', 'zookeeper.connected')
@when_not('zookeeper.available')
def waiting_for_zookeeper_available(zk):
    hookenv.status_set('waiting', 'Waiting for Zookeeper to become ready')


@when('kafka.installed', 'zookeeper.joining', 'zookeeper.available')
@when_not('kafka.started')
def configure_kafka(zkjoining, zkavailable):
    try:
        zk_units = zkavailable.get_zookeeper_units()
        hookenv.status_set('maintenance', 'Setting up Kafka')
        kafka = Kafka(dist_config())
        kafka.configure_kafka(zk_units)
        kafka.start()
        zkjoining.dismiss_joining()
        hookenv.status_set('active', 'Ready')
        set_state('kafka.started')
    except:
        hookenv.log("Relation with Zookeeper not established")        
    

@when('kafka.started', 'zookeeper.joining', 'zookeeper.available')
def reconfigure_kafka_new_zk_instances(zkjoining, zkavailable):
    try:
        zk_units = zkavailable.get_zookeeper_units()
        hookenv.status_set('maintenance', 'Updating Kafka with new Zookeeper instances')
        kafka = Kafka(dist_config())
        kafka.configure_kafka(zk_units)
        kafka.restart()
        zkjoining.dismiss_joining()
        hookenv.status_set('active', 'Ready')
    except:
        hookenv.log("Relation with Zookeeper not established")        


@when('kafka.started', 'zookeeper.departing', 'zookeeper.available')
def reconfigure_kafka_zk_instances_leaving(zkdeparting, zkavailable):
    try:
        zk_units = zkavailable.get_zookeeper_units()
        hookenv.status_set('maintenance', 'Updating Kafka with departing Zookeeper instances ')
        kafka = Kafka(dist_config())
        kafka.configure_kafka(zk_units)
        kafka.restart()
        zkdeparting.dismiss_departing()
        hookenv.status_set('active', 'Ready')
    except:
        hookenv.log("Relation with Zookeeper not established. Stopping Kafka.")        
        kafka = Kafka(dist_config())
        kafka.stop()
        remove_state('kafka.started')
        hookenv.status_set('blocked', 'Waiting for connection to Zookeeper')


@when('kafka.connected')
@when_not('kafka.available')
def waiting_availuable_flume(kafka_client):
    port = dist_config().exposed_ports('kafka')[0]
    kafka_client.send_configuration(port)    
    hookenv.log('Sending configuration to client')

