"""Ryu OpenFlow 1.3 controller with static and worker-load-based routing."""
import json
import os

from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import (
    CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls,
)
from ryu.lib import hub
from ryu.ofproto import ofproto_v1_3

from config import (
    HOST_IPS, WORKER_IPS, S1_HOST_PORTS, S4_WORKER_PORTS,
    S1_TO_S2_PORT, S1_TO_S3_PORT, S2_TO_S4_PORT, S3_TO_S4_PORT,
    S2_TO_S1_PORT, S3_TO_S1_PORT, S4_TO_S2_PORT, S4_TO_S3_PORT,
    LOAD_FILE,
)

MODE = os.environ.get('SDN_MODE', 'dynamic').strip().lower()


class TaskController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super(TaskController, self).__init__(*args, **kwargs)
        self.switches = {}
        # Preserve original static default: both workers use the s1-s2-s4 path.
        # Dynamic mode changes these values using the same load-selection rule.
        self.routes = {ip: 2 for ip in WORKER_IPS}
        self.logger.info('SDN mode: %s', MODE)
        if MODE not in ('static', 'dynamic'):
            self.logger.warning(
                'Unknown SDN_MODE=%s; using static routing', MODE
            )
        hub.spawn(self.check_load)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        self.switches[dp.id] = dp
        self.install_for_switch(dp)
        self.logger.info('Configured switch s%s', dp.id)

    @set_ev_cls(ofp_event.EventOFPStateChange,
                [MAIN_DISPATCHER, DEAD_DISPATCHER])
    def state_change(self, ev):
        dp = ev.datapath
        if ev.state == DEAD_DISPATCHER and self.switches.get(dp.id) is dp:
            del self.switches[dp.id]

    def add_flow(self, dp, source, destination, port):
        parser = dp.ofproto_parser
        ofp = dp.ofproto
        match = parser.OFPMatch(
            eth_type=0x0800, ipv4_src=source, ipv4_dst=destination
        )
        actions = [parser.OFPActionOutput(port)]
        instructions = [
            parser.OFPInstructionActions(ofp.OFPIT_APPLY_ACTIONS, actions)
        ]
        # Re-adding the same match and priority updates the selected output port.
        dp.send_msg(parser.OFPFlowMod(
            datapath=dp, priority=10, match=match,
            instructions=instructions,
        ))

    def install_for_switch(self, dp):
        """Install host-pair flows for the existing four-switch diamond.

        Server and clients are connected to s1; workers are connected to s4.
        The two core paths remain s1-s2-s4 and s1-s3-s4.
        """
        left = S1_HOST_PORTS
        right = S4_WORKER_PORTS

        for src in HOST_IPS:
            for dst in HOST_IPS:
                if src == dst:
                    continue

                if dp.id == 1:  # s1: server/client access and path selection
                    if dst in left:
                        port = left[dst]
                    elif src in left and dst in right:
                        port = (S1_TO_S2_PORT if self.routes[dst] == 2
                                else S1_TO_S3_PORT)
                    else:
                        continue

                elif dp.id == 4:  # s4: worker access and reverse path selection
                    if dst in right:
                        port = right[dst]
                    elif src in right and dst in left:
                        port = (S4_TO_S2_PORT if self.routes[src] == 2
                                else S4_TO_S3_PORT)
                    else:
                        continue

                elif dp.id == 2:  # s2: upper path
                    if src in left and dst in right:
                        port = S2_TO_S4_PORT
                    elif src in right and dst in left:
                        port = S2_TO_S1_PORT
                    else:
                        continue

                elif dp.id == 3:  # s3: lower path
                    if src in left and dst in right:
                        port = S3_TO_S4_PORT
                    elif src in right and dst in left:
                        port = S3_TO_S1_PORT
                    else:
                        continue
                else:
                    continue

                self.add_flow(dp, src, dst, port)

    def check_load(self):
        while True:
            # Static mode deliberately never reads the load file or changes routes.
            if MODE == 'dynamic':
                try:
                    with open(LOAD_FILE, encoding='utf-8') as f:
                        load = json.load(f)

                    # Preserve the original dynamic rule:
                    # the busiest worker gets path 2; when both workers are
                    # busy, the less-loaded worker is moved to path 3.
                    order = sorted(
                        self.routes,
                        key=lambda ip: (-int(load.get(ip, 0)), ip),
                    )
                    routes = {
                        order[0]: 2,
                        order[1]: (3 if int(load.get(order[1], 0)) > 0 else 2),
                    }
                    if routes != self.routes:
                        self.routes = routes
                        for dp in list(self.switches.values()):
                            self.install_for_switch(dp)
                        self.logger.info(
                            'Workloads %s; updated routes %s', load, routes
                        )
                except (OSError, ValueError, TypeError):
                    # The server may not have created the load file yet.
                    pass
            hub.sleep(0.5)
