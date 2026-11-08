"""Three-client, one-server, two-worker Mininet diamond topology."""
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel

from config import (
    SERVER_HOST, SERVER_IP, WORKERS, CLIENTS,
    S1_HOST_PORTS, S4_WORKER_PORTS,
    S1_TO_S2_PORT, S1_TO_S3_PORT,
    S2_TO_S1_PORT, S2_TO_S4_PORT,
    S3_TO_S1_PORT, S3_TO_S4_PORT,
    S4_TO_S2_PORT, S4_TO_S3_PORT,
    CORE_LINK_BANDWIDTH_MBPS, CORE_LINK_DELAY,
)


class TaskTopology(Topo):
    def build(self):
        server = self.addHost(SERVER_HOST, ip=SERVER_IP + '/24')
        worker_hosts = [
            self.addHost(name, ip=ip + '/24')
            for name, ip, _ in WORKERS
        ]
        client_hosts = [
            self.addHost(name, ip=ip + '/24')
            for name, ip, _ in CLIENTS
        ]

        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', protocols='OpenFlow13')

        # Server and all clients attach to s1. Explicit switch ports preserve
        # the original server/client and diamond-uplink port assignments.
        self.addLink(server, s1, port2=S1_HOST_PORTS[SERVER_IP])
        for host, (_, ip, _) in zip(client_hosts, CLIENTS):
            self.addLink(host, s1, port2=S1_HOST_PORTS[ip])

        # Keep the original diamond links and their fixed ports unchanged.
        link_options = {
            'bw': CORE_LINK_BANDWIDTH_MBPS,
            'delay': CORE_LINK_DELAY,
        }
        self.addLink(s1, s2, port1=S1_TO_S2_PORT,
                     port2=S2_TO_S1_PORT, **link_options)
        self.addLink(s1, s3, port1=S1_TO_S3_PORT,
                     port2=S3_TO_S1_PORT, **link_options)
        self.addLink(s2, s4, port1=S2_TO_S4_PORT,
                     port2=S4_TO_S2_PORT, **link_options)
        self.addLink(s3, s4, port1=S3_TO_S4_PORT,
                     port2=S4_TO_S3_PORT, **link_options)

        # Both existing workers remain attached to s4 on their original ports.
        for host, (_, ip, switch_port) in zip(worker_hosts, WORKERS):
            self.addLink(host, s4, port2=S4_WORKER_PORTS[ip])


if __name__ == '__main__':
    setLogLevel('info')
    net = Mininet(topo=TaskTopology(), switch=OVSSwitch, controller=None,
                  link=TCLink, autoSetMacs=True, autoStaticArp=True)
    net.addController('c0', controller=RemoteController,
                      ip='127.0.0.1', port=6653)
    try:
        net.start()
        print('\nTopology: 3 clients, 1 server, 2 workers, 4 switches.')
        print('Wait for Ryu to install the flows, then run pingall.')
        CLI(net)
    finally:
        net.stop()
