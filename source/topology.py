"""Mininet diamond topology. Port numbers are fixed for controller.py."""
from mininet.cli import CLI
from mininet.link import TCLink
from mininet.net import Mininet
from mininet.node import RemoteController, OVSSwitch
from mininet.topo import Topo
from mininet.log import setLogLevel


class TaskTopology(Topo):
    def build(self):
        h1 = self.addHost('h1', ip='10.0.0.1/24')  # server
        h2 = self.addHost('h2', ip='10.0.0.2/24')  # worker
        h3 = self.addHost('h3', ip='10.0.0.3/24')  # worker
        h4 = self.addHost('h4', ip='10.0.0.4/24')  # client
        s1 = self.addSwitch('s1', protocols='OpenFlow13')
        s2 = self.addSwitch('s2', protocols='OpenFlow13')
        s3 = self.addSwitch('s3', protocols='OpenFlow13')
        s4 = self.addSwitch('s4', protocols='OpenFlow13')
        self.addLink(h1, s1, port2=1)
        self.addLink(h4, s1, port2=2)
        self.addLink(s1, s2, port1=3, port2=1, bw=10, delay='5ms')
        self.addLink(s1, s3, port1=4, port2=1, bw=10, delay='5ms')
        self.addLink(s2, s4, port1=2, port2=3, bw=10, delay='5ms')
        self.addLink(s3, s4, port1=2, port2=4, bw=10, delay='5ms')
        self.addLink(h2, s4, port2=1)
        self.addLink(h3, s4, port2=2)


if __name__ == '__main__':
    setLogLevel('info')
    net = Mininet(topo=TaskTopology(), switch=OVSSwitch, controller=None,
                  link=TCLink, autoSetMacs=True, autoStaticArp=True)
    net.addController('c0', controller=RemoteController, ip='127.0.0.1', port=6653)
    try:
        net.start()
        print('\nWait a few seconds for Ryu to install the flows, then use pingall.')
        CLI(net)
    finally:
        net.stop()
