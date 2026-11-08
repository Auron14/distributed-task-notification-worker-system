"""Central configuration for the Mininet SDN task-processing project.

To extend the topology later, update the host tuples and matching switch-port
assignments here, then extend the controller's routing groups if new roles are
introduced. The current target is 3 clients, 1 server and 2 workers.
"""

# Application endpoints
SERVER_HOST = 'h1'
SERVER_IP = '10.0.0.1'
SERVER_PORT = 5000

# (Mininet host name, IPv4 address, access-switch port)
WORKERS = (
    ('h2', '10.0.0.2', 1),
    ('h3', '10.0.0.3', 2),
)
CLIENTS = (
    ('h4', '10.0.0.4', 2),
    ('h5', '10.0.0.5', 5),
    ('h6', '10.0.0.6', 6),
)

WORKER_IPS = tuple(ip for _, ip, _ in WORKERS)
CLIENT_IPS = tuple(ip for _, ip, _ in CLIENTS)
HOST_IPS = (SERVER_IP,) + WORKER_IPS + CLIENT_IPS

# Fixed access ports. Core diamond links retain their original port numbers.
S1_HOST_PORTS = {
    SERVER_IP: 1,
    **{ip: switch_port for _, ip, switch_port in CLIENTS},
}
S4_WORKER_PORTS = {
    ip: switch_port for _, ip, switch_port in WORKERS
}

# Existing four-switch diamond port assignments.
S1_TO_S2_PORT = 3
S1_TO_S3_PORT = 4
S2_TO_S1_PORT = 1
S2_TO_S4_PORT = 2
S3_TO_S1_PORT = 1
S3_TO_S4_PORT = 2
S4_TO_S2_PORT = 3
S4_TO_S3_PORT = 4

# Scheduling and processing. Keep server capacity and worker parallelism equal:
# the server should not send more simultaneous jobs than a worker can execute.
WORKER_CAPACITY = 2
WORKER_PARALLELISM = 2
TASK_TIMEOUT = 16
HEARTBEAT_TIMEOUT = 8
MAX_ATTEMPTS = 3
LOAD_FILE = '/tmp/sdn_worker_load.json'

# Request validation and client defaults.
MAX_BATCH_SIZE = 100
MAX_ABS_NUMBER = 1_000_000
DEFAULT_TASK_DELAY = 3.0
MAX_TASK_DELAY = 5.0
CLIENT_RESPONSE_TIMEOUT = 120

# Mininet link characteristics between the four switches.
CORE_LINK_BANDWIDTH_MBPS = 10
CORE_LINK_DELAY = '5ms'
