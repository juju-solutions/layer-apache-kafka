## Overview

Apache Kafka is an open-source message broker project developed by the Apache
Software Foundation written in Scala. The project aims to provide a unified,
high-throughput, low-latency platform for handling real-time data feeds. Learn
more at [kafka.apache.org](http://kafka.apache.org/).


## Usage

Kafka requires the Zookeeper distributed coordination service. Deploy and
relate them as follows:

    juju deploy apache-zookeeper zookeeper
    juju deploy apache-kafka kafka
    juju add-relation kafka zookeeper

Once deployed, we can list the zookeeper servers that our kafka brokers
are connected to. The following will list `<ip>:<port>` information for each
zookeeper unit in the environment (e.g.: `10.0.3.221:2181`).

    juju action do kafka/0 list-zks
    juju action fetch <id>  # <-- id from above command

We can create a Kafka topic with:

    juju action do kafka/0 create-topic topic=<topic_name> \
     partitions=<#> replication=<#>
    juju action fetch <id>  # <-- id from above command

We can list topics with:

    juju action do kafka/0 list-topics
    juju action fetch <id>  # <-- id from above command

We can write to a topic with:

    juju action do kafka/0 write-topic topic=<topic_name> data=<data>
    juju action fetch <id>  # <-- id from above command

We can read from a topic with:

    juju action do kafka/0 read-topic topic=<topic_name> partition=<#>
    juju action fetch <id>  # <-- id from above command

And finally, we can delete a topic with:

    juju action do kafka/0 delete-topic topic=<topic_name>
    juju action fetch <id>  # <-- id from above command


## Status and Smoke Test

Kafka provides extended status reporting to indicate when it is ready:

    juju status --format=tabular

This is particularly useful when combined with `watch` to track the on-going
progress of the deployment:

    watch -n 0.5 juju status --format=tabular

The message for each unit will provide information about that unit's state.
Once they all indicate that they are ready, you can perform a "smoke test"
to verify that Kafka is working as expected using the built-in `smoke-test`
action:

    juju action do kafka/0 smoke-test

After a few seconds or so, you can check the results of the smoke test:

    juju action status

You will see `status: completed` if the smoke test was successful, or
`status: failed` if it was not.  You can get more information on why it failed
via:

    juju action fetch <action-id>


## Scaling

Creating a cluster with many brokers is as easy as adding more units to your
Kafka service:

    juju add-unit kafka

After adding additional brokers, you will be able to create topics with
replication up to the number of kafka units.

To verify replication is working you can do the following:

    juju add-unit kafka -n 2
    juju action do kafka/0 create-topic topic=my-replicated-topic \
        partitions=1 replication=2

Query for the description of the just created topic:

    juju ssh kafka/0
    kafka-topics.sh --describe --topic my-replicated-topic \
        --zookeeper <zookeeperip>:2181

You should get a response similar to:

    Topic: my-replicated-topic PartitionCount:1 ReplicationFactor:2 Configs:
    Topic: my-replicated-topic Partition: 0 Leader: 2 Replicas: 2,0 Isr: 2,0


## Connecting External Clients

By default, this charm does not expose Kafka outside of the provider's network.
To allow external clients to connect to Kafka, first expose the service:

    juju expose kafka

Next, ensure the external client can resolve the short hostname of the kafka
unit. A simple way to do this is to add an `/etc/hosts` entry on the external
kafka client machine. Gather the needed info from juju:

    user@juju-client$ juju run --unit kafka/0 'hostname -s'
    kafka-0
    user@juju-client$ juju status --format=yaml kafka/0 | grep public-address
    public-address: 40.784.149.135

Update `/etc/hosts` on the external kafka client:

    user@kafka-client$ echo "40.784.149.135 kafka-0" | sudo tee -a /etc/hosts

The external kafka client should now be able to access Kafka by using
`kafka-0:9092` as the broker.


## Deploying in Network-Restricted Environments

This charm can be deployed in environments with limited network access. To
deploy in this environment, you will need a local mirror to serve the packages
and resources required by this charm.

### Mirroring Packages

You can setup a local mirror for apt packages using squid-deb-proxy.
For instructions on configuring juju to use this, see the
[Juju Proxy Documentation](https://juju.ubuntu.com/docs/howto-proxies.html).

### Mirroring Resources

In addition to apt packages, this charm requires a few binary resources
which are normally hosted on Launchpad. If access to Launchpad is not
available, the `jujuresources` library makes it easy to create a mirror
of these resources:

    sudo pip install jujuresources
    juju-resources fetch --all /path/to/resources.yaml -d /tmp/resources
    juju-resources serve -d /tmp/resources

This will fetch all of the resources needed by this charm and serve them via a
simple HTTP server. The output from `juju-resources serve` will give you a
URL that you can set as the `resources_mirror` config option for this charm.
Setting this option will cause all resources required by this charm to be
downloaded from the configured URL.


## Contact Information
- <bigdata@lists.ubuntu.com>


## Help
- [Apache Kafka home page](http://kafka.apache.org/)
- [Apache Kafka issue tracker](https://issues.apache.org/jira/browse/KAFKA)
- [Juju mailing list](https://lists.ubuntu.com/mailman/listinfo/juju)
- [Juju community](https://jujucharms.com/community)
