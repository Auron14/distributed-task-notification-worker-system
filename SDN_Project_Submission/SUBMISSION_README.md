# SDN Project Submission Bundle

## Contents
- `sdn-task-project-integrated.zip`: project source package and `PERFORMANCE_RESULTS.md`.
- `README.md`: setup guide copied from the supplied project README.
- `screenshots/`: screenshots captured during the demonstrated tests.

## Evidence included
1. Ryu controller running in dynamic mode.
2. Mininet `pingall` success.
3. TCP task processing and worker registration.
4. Workload updates and route decisions in Ryu.
5. OpenFlow forwarding-rule inspection.
6. Worker disconnection, requeue/reassignment, and completion of eight tasks.
7. Three static and three dynamic performance trials.

## Recorded performance measurements

| Mode | Trial | Completion time (s) | Throughput (tasks/s) | Success / failed |
|---|---:|---:|---:|---:|
| Static | 1 | 18.26 | 0.66 | 12 / 0 |
| Static | 2 | 19.15 | 0.63 | 12 / 0 |
| Static | 3 | 20.18 | 0.59 | 12 / 0 |
| Dynamic | 1 | 19.50 | 0.62 | 12 / 0 |
| Dynamic | 2 | 18.67 | 0.64 | 12 / 0 |
| Dynamic | 3 | 20.52 | 0.58 | 12 / 0 |

Medians transcribed from the screenshots: static completion time 19.15 s; dynamic completion time 19.50 s. These measurements do not show a speed improvement for dynamic routing in this small workload. The screenshots document observed runs; the full environment was not rerun during packaging.

## Before submission
- Review the ZIP and README on the demonstration laptop.
- Confirm the Ryu mode and that both workers start freshly for each performance trial.
- Keep the original ZIP as a backup.
