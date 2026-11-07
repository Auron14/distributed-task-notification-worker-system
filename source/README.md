# Distributed Task Notification and Worker System

This is a small TCP socket project for Mininet and the Ryu SDN controller. A client submits numbers; the workers calculate their squares and send the results back. The delay in each task simulates work so that workload, routing changes and failure recovery are easy to observe.

## 1. Files

| File | Purpose |
| --- | --- |
| `common.py` | Sends and receives newline-separated JSON messages over TCP. |
| `server.py` | Registers workers, tracks their workload, assigns tasks and retries failed work. |
| `worker.py` | Connects to the server, sends heartbeats and calculates results. |
| `client.py` | Submits a batch and prints results, elapsed time and throughput. |
| `topology.py` | Creates the four-host, four-switch Mininet topology. |
| `controller.py` | Ryu controller that installs and updates OpenFlow 1.3 rules. |

All six `.py` files must be in the same folder. Run the commands below in your **Linux Mininet/Ryu VM or machine**, not in Windows PowerShell. If Mininet is in a VM, copy the entire folder into the VM using your usual shared folder or file-transfer method. Both Ryu and Mininet must use the same VM and shared filesystem.

## 2. Architecture

```text
h1: server ---- s1 ---- s2 ---- s4 ---- h2: worker
                  \              /  \--- h3: worker
h4: client ---- s1 ---- s3 ---- s4
```

* h1 (10.0.0.1) runs the task server; h4 (10.0.0.4) runs the client.
* h2 (10.0.0.2) and h3 (10.0.0.3) are workers. Each worker executes one task at a time, with up to two assigned tasks including any waiting in its TCP connection.
* The server chooses the connected worker with the fewest outstanding tasks. It writes worker loads to `/tmp/sdn_worker_load.json`. This is a local shared file used for application-to-controller communication; the tasks, results and heartbeats themselves use TCP sockets.
* Ryu reads the file every 0.5 seconds. When both workers have outstanding work, Ryu assigns one worker's traffic to s2 and the other's to s3. Otherwise it uses s2. Ryu updates the IPv4 flow entries on the switches; it does not schedule the tasks itself.
* Static comparison mode uses s2 for both workers throughout. Scheduling is unchanged. The switches have fixed port numbers, and the topology installs static ARP entries to avoid broadcast loops in the diamond.

The routing rule uses **application workload as a simple traffic proxy**; it does not measure actual link utilization. The project detects worker failures, not switch or link failures. Because square tasks exchange very little data, the dynamic route is not guaranteed to improve completion time. Do not claim an improvement unless your measurements show one.

## 3. Start the project

Open two Linux terminals in the same VM. In each terminal, go to the project folder, for example:

```bash
cd ~/sdn-task-project
```

Replace that path with the folder where you copied the files. Check `pwd` and `ls` if necessary. You need Python 3, Ryu, Mininet and Open vSwitch installed. This project uses only Python's standard library for the application; Ryu and Mininet are separate system dependencies.

### Terminal 1: start Ryu

```bash
rm -f /tmp/sdn_worker_load.json
SDN_MODE=dynamic ryu-manager --ofp-tcp-listen-port 6653 controller.py
```

Leave this terminal running. A Python virtual environment or the actual `ryu-manager` path may be needed depending on how Ryu is installed. Ryu must listen on port 6653, matching `topology.py`.

### Terminal 2: start Mininet

```bash
cd ~/sdn-task-project
sudo python3 topology.py
```

The prompt becomes `mininet>`. Wait a few seconds for all four switches to connect, then enter:

```text
pingall
```

All four hosts should be able to ping each other. If the first ping fails while flows are still being installed, wait a few seconds and run `pingall` again. In Terminal 1, look for `Configured switch s1` through `s4`.

### At the Mininet prompt: start the server and workers

Run these **one line at a time**, without typing `mininet>`:

```text
h1 sh -c 'python3 -u server.py > /tmp/task_server.log 2>&1 & echo $! > /tmp/server.pid'
h2 sh -c 'python3 -u worker.py > /tmp/worker2.log 2>&1 & echo $! > /tmp/worker2.pid'
h3 sh -c 'python3 -u worker.py > /tmp/worker3.log 2>&1 & echo $! > /tmp/worker3.pid'
```

Wait about five seconds, then check:

```text
sh cat /tmp/task_server.log
sh cat /tmp/worker2.log
sh cat /tmp/worker3.log
```

The server log should show that both 10.0.0.2 and 10.0.0.3 registered. If a worker started before the server, it retries automatically. The server accepts workers only from those two host IPs.

### Submit a batch

```text
h4 python3 -u client.py --count 6 --delay 3
```

This submits the numbers 1 to 6. Each task sleeps for 3 seconds and returns its square. You should see six results, the worker IP for each, the number of attempts, total elapsed time and successful tasks per second. Results may arrive in a different order.

While tasks are running, Terminal 1 should show `Workloads ... updated routes ...`. You can also inspect the current load and switch flows at the Mininet prompt:

```text
sh cat /tmp/sdn_worker_load.json
sh ovs-ofctl -O OpenFlow13 dump-flows s1
sh ovs-ofctl -O OpenFlow13 dump-flows s4
```

On s1, output port 3 goes toward s2 and output port 4 goes toward s3. On s4, ports 3 and 4 lead back through s2 and s3 respectively. `nw_src` and `nw_dst` in the flow output identify the relevant host pair. Flow entries can change again after a batch finishes because the load returns to zero.

## 4. Demonstrate worker failure and task redistribution

First check both workers are registered. Then start a longer batch in the background:

```text
h4 sh -c 'python3 -u client.py --count 8 --delay 5 > /tmp/failure_demo.log 2>&1 &'
```

Within a couple of seconds, stop only worker h2 using its recorded process ID:

```text
h2 kill $(cat /tmp/worker2.pid)
```

Wait approximately 40 seconds for the remaining worker to finish, then inspect:

```text
sh cat /tmp/task_server.log
sh cat /tmp/failure_demo.log
```

The server should report that h2 was removed and its unfinished tasks were requeued. The client should eventually show eight successful results, with `attempts 2` for at least one task reassigned to h3. If h2 is stopped before it receives a task, start it again and repeat the test. To restart it:

```text
h2 sh -c 'python3 -u worker.py > /tmp/worker2.log 2>&1 & echo $! > /tmp/worker2.pid'
```

In addition to a closed connection, the server detects missing heartbeats after 8 seconds and removes a worker if a task has been assigned for more than 16 seconds. Its unfinished tasks are retried, up to three attempts. With no workers available, tasks wait in the server queue; the client waits up to 120 seconds for each next message. Tasks are pure calculations, so retrying them is safe; a task can be executed more than once after a timeout, and obsolete results are ignored.

## 5. Performance comparison for the rubric

Keep the topology, both workers, task count and delay the same in both modes. Use a clean run for each mode:

1. Start in `dynamic` mode as above. With both workers connected, run `h4 python3 -u client.py --count 12 --delay 3` three times. Record each elapsed time and throughput. Confirm route updates in the Ryu terminal.
2. Stop the three background processes using the commands in section 6, then enter `exit` at the Mininet prompt. Stop Ryu with Ctrl+C. If Mininet did not shut down cleanly, run `sudo mn -c` **only after exiting the project**.
3. Remove the old load file and start the controller in static mode:

   ```bash
   rm -f /tmp/sdn_worker_load.json
   SDN_MODE=static ryu-manager --ofp-tcp-listen-port 6653 controller.py
   ```

4. Start the topology, server and both workers again exactly as in section 3. Run the same batch three times and record results. Static mode keeps both worker paths through s2.
5. Compare the median completion time and median throughput, and note success/failure counts. Include the separate worker-failure test from section 4 as the robustness scenario.

| Mode | Trial | Tasks | Completion time (s) | Successful tasks/sec | Successful / failed |
| --- | --- | --- | --- | --- | --- |
| Dynamic | 1 | 12 | measure | measure | measure |
| Dynamic | 2 | 12 | measure | measure | measure |
| Dynamic | 3 | 12 | measure | measure | measure |
| Static | 1 | 12 | measure | measure | measure |
| Static | 2 | 12 | measure | measure | measure |
| Static | 3 | 12 | measure | measure | measure |

These are spaces for **your own measurements**, not predicted results. The task delay dominates this experiment; similar values are a valid result. State the VM, Mininet/Ryu versions and any other relevant conditions when presenting the results.

## 6. Troubleshooting and cleanup

* `pingall` fails: verify Ryu is running on 6653, both terminals are on the same VM, all four switch connection messages appear, and the files were copied without edits. Use `sudo ovs-vsctl show` in a separate VM terminal to inspect the controller connections.
* Workers do not register: inspect all three `/tmp/*.log` files above, check h1 is 10.0.0.1 and run `h2 ping -c 2 10.0.0.1`. Verify server and workers were started from the project folder.
* `Address already in use`: a previous server may still be running. Exit the old Mininet session and check the process identified by `/tmp/server.pid` before stopping it. Do not start a second server on port 5000.
* To stop cleanly, stop the processes you started, enter `exit` in Mininet, then press Ctrl+C in the Ryu terminal:

  ```text
  h1 kill $(cat /tmp/server.pid)
  h2 kill $(cat /tmp/worker2.pid)
  h3 kill $(cat /tmp/worker3.pid)
  exit
  ```

  If you have already stopped a worker, its `kill` command may report that the process does not exist. The PID files refer to the processes started in the current demo; check them before using them after a restart.
* The project is designed for a local educational Mininet setup. It does not provide authentication, encryption, persistent queues, link-failure recovery, or production-grade isolation.

For the final submission, copy these files and your real measurements into your own GitHub repository, as required by your rubric. Explain the protocol, the least-loaded scheduling, the shared-file connection to Ryu, and what you observed during the failure test.
