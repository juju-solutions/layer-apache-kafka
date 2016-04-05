import re
import sys
import yaml

from charmhelpers.core import hookenv


def fail(msg, output):
    hookenv.action_set({'output': output})
    hookenv.action_fail(msg)
    sys.exit()


def get_zookeepers():
    with open("dist.yaml", 'r') as distconf:
        config = yaml.load(distconf)

    cfg = '/'.join((config["dirs"]["kafka_conf"]["path"], 'server.properties'))
    print(cfg)
    file = open(cfg, "r")

    for line in file:
        if re.search('^zookeeper.connect=.*', line):
            zks = line.split("=")[1].strip('\n')
            return zks

    return None
