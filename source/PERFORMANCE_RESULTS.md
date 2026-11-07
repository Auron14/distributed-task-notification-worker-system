# Performance and Integration Evidence

## Functional tests observed

The following results were observed in the user's terminal screenshots; they are runtime observations, not a fresh execution performed while packaging this archive.

- Mininet connectivity: `0% dropped (12/12 received)`.
- Normal task batch: 6 tasks successful, 0 failed.
- Worker failure/recovery batch: 8 tasks successful, 0 failed; the server detected worker `10.0.0.2` disconnecting, requeued unfinished tasks, and reassigned work to `10.0.0.3`.
- Dynamic controller log showed all four switches configured and workload-based route updates.

## Static versus dynamic performance

Each run submitted 12 tasks with `--delay 3`. Values below were transcribed from the user's screenshots.

| Mode | Trial | Tasks | Completion time (s) | Throughput (tasks/s) | Successful / failed |
|---|---:|---:|---:|---:|---:|
| Static | 1 | 12 | 18.26 | 0.66 | 12 / 0 |
| Static | 2 | 12 | 19.15 | 0.63 | 12 / 0 |
| Static | 3 | 12 | 20.18 | 0.59 | 12 / 0 |
| Dynamic | 1 | 12 | 19.50 | 0.62 | 12 / 0 |
| Dynamic | 2 | 12 | 18.67 | 0.64 | 12 / 0 |
| Dynamic | 3 | 12 | 20.52 | 0.58 | 12 / 0 |

| Metric | Static median | Dynamic median |
|---|---:|---:|
| Completion time (s) | 19.15 | 19.50 |
| Throughput (tasks/s), median of displayed rounded rates | 0.63 | 0.62 |

Dynamic median completion time was about 1.8% higher (slower) than static in these trials. Do not claim dynamic routing improved performance for this workload. Small square-computation tasks exchange little data, and measured times can be dominated by simulated task delays and VM overhead.

## Reproducibility note

The measurements are transcribed from screenshots. Before presenting them as a controlled experiment, ensure each trial used the intended `SDN_MODE`, the same topology and workload, and freshly registered workers. The user observed `bash: hsh: command not found` during one startup attempt, although the client batches shown completed successfully. Record the VM and Ryu/Mininet versions in the final report if required.
