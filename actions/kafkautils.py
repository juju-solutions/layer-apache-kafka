import re
import yaml

def get_zookeepers():
    with open("dist.yaml", 'r') as distconf:
        config = yaml.load(distconf)

    cfg = '/'.join((config["dirs"]["kafka_conf"]["path"], 'consumer.properties'))
    print(cfg)
    file = open(cfg, "r")

    for line in file:
        if re.search('^zookeeper.connect=.*', line):
            zks = line.split("=")[1].strip('\n')
            return zks

    return None
