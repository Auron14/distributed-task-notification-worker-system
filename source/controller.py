"""Ryu OpenFlow 1.3 controller with worker-load-based path selection."""
import json
import os
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

LOAD_FILE = '/tmp/sdn_worker_load.json'
MODE = os.environ.get('SDN_MODE', 'dynamic')
IPS = ('10.0.0.1', '10.0.0.2', '10.0.0.3', '10.0.0.4')


class TaskController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TaskController, self).__init__(*args, **kwargs)
        self.switches = {}
        self.routes = {'10.0.0.2': 2, '10.0.0.3': 2}
        self.logger.info('SDN mode: %s', MODE)
        hub.spawn(self.check_load)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        self.switches[dp.id] = dp
        self.install_for_switch(dp)
        self.logger.info('Configured switch s%s', dp.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change(self, ev):
        dp = ev.datapath
        if ev.state == DEAD_DISPATCHER and self.switches.get(dp.id) is dp:
            del self.switches[dp.id]

    def add_flow(self, dp, source, destination, port):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        match = parser.OFPMatch(eth_type=0x0800, ipv4_src=source, ipv4_dst=destination)
        actions = [parser.OFPActionOutput(port)]
        instructions = [parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)]
        # OFPFC_ADD replaces the existing entry with the same match and priority.
        dp.send_msg(parser.OFPFlowMod(datapath=dp, priority=10, match=match,
                                     instructions=instructions))

    def install_for_switch(self, dp):
        left = {'10.0.0.1': 1, '10.0.0.4': 2}
        right = {'10.0.0.2': 1, '10.0.0.3': 2}
        for src in IPS:
            for dst in IPS:
                if src == dst:
                    continue
                if dp.id == 1:
                    if dst in left:
                        port = left[dst]
                    elif src in left:
                        port = 3 if self.routes[dst] == 2 else 4
                    else:
                        continue
                elif dp.id == 4:
                    if dst in right:
                        port = right[dst]
                    elif src in right:
                        port = 3 if self.routes[src] == 2 else 4
                    else:
                        continue
                elif dp.id in (2, 3):
                    if src in left and dst in right:
                        port = 2
                    elif src in right and dst in left:
                        port = 1
                    else:
                        continue
                else:
                    continue
                self.add_flow(dp, src, dst, port)

    def check_load(self):
        while True:
            if MODE == 'dynamic':
                try:
                    with open(LOAD_FILE, encoding='utf-8') as f:
                        load = json.load(f)
                    # When both workers are busy, spread their traffic over
                    # the two paths. Otherwise use the upper path for both.
                    order = sorted(self.routes, key=lambda ip: (-int(load.get(ip, 0)), ip))
                    routes = {order[0]: 2, order[1]: 3 if int(load.get(order[1], 0)) > 0 else 2}
                    if routes != self.routes:
                        self.routes = routes
                        for dp in list(self.switches.values()):
                            self.install_for_switch(dp)
                        self.logger.info('Workloads %s; updated routes %s', load, routes)
                except (OSError, ValueError, TypeError):
                    pass
            hub.sleep(0.5)
