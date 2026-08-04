# Workflow Provenance Card: 07-mol-design

## Summary
- **Workflow Name:** `07-mol-design`
- **Workflow ID:** `7d081bbb-bbfd-4f13-b4c6-839c03925d5b`
- **Campaign ID:** `735e36cf-4234-4b81-b0dd-a98463b215f3`
- **Execution Start (UTC):** `2026-08-04 04:05:13`
- **Execution End (UTC):** `2026-08-04 04:09:56`
- **Total Elapsed (s):** `282.304`

## Workflow-level Summary
- **Total Activities:** `13`
- **Status Counts:** `{'FINISHED': 22, 'ERROR': 9}`
- **Total Elapsed Workflow Time (s):** `282.304`
- **Top 5 Slowest Activities:**
  - `conduct_simulation_campaign`: `141.152 s`
  - `simulate`: `120.786 s`
  - `critique`: `12.126 s`
  - `update`: `9.066 s`
  - `plan`: `8.864 s`
- **Resource Totals:**
  - `Memory Used`: `1.42 GB`
  - `Average CPU (%)`: `19.5%`
- **Key Observations:**
  - Slowest Activity: `conduct_simulation_campaign` at `141.152 s`

## Workflow Structure

```text
   input
     │
     ▼
 conduct_simulation_campaign
     │
 agent_startup
     │
 plan
     │
 gpt-4o-2024-11-20
     │
 tool_calling
     │
 simulate
     │
 compute_ionization_energy
     │
 conclude
     │
 should_continue
     │
 critique
     │
 update
     │
 report
     │
 agent_shutdown
     ▼
   output
```

## Timing Report
Rows are sorted by **First Started At** (ascending).

| Activity | Status Counts | First Started At | Last Ended At | Median Elapsed (s) |
| --- | --- | --- | --- | --- |
| conduct_simulation_campaign | {'FINISHED': 2} | 2026-08-04 04:05:13 | 2026-08-04 04:09:56 | 141.152 |
| agent_startup | {'FINISHED': 1} | 2026-08-04 04:05:16 | 2026-08-04 04:05:16 | 0.000 |
| plan | {'FINISHED': 1} | 2026-08-04 04:05:16 | 2026-08-04 04:05:25 | 8.864 |
| gpt-4o-2024-11-20 | {'FINISHED': 6} | 2026-08-04 04:05:16 | 2026-08-04 04:05:54 | 6.309 |
| tool_calling | {'FINISHED': 2} | 2026-08-04 04:05:25 | 2026-08-04 04:05:54 | 1.516 |
| simulate | {'FINISHED': 1, 'ERROR': 1} | 2026-08-04 04:05:26 | 2026-08-04 04:09:55 | 120.786 |
| compute_ionization_energy | {'ERROR': 8, 'FINISHED': 2} | 2026-08-04 04:05:26 | 2026-08-04 04:09:55 | 0.418 |
| conclude | {'FINISHED': 1} | 2026-08-04 04:05:27 | 2026-08-04 04:05:30 | 3.792 |
| should_continue | {'FINISHED': 1} | 2026-08-04 04:05:30 | 2026-08-04 04:05:30 | 0.008 |
| critique | {'FINISHED': 1} | 2026-08-04 04:05:30 | 2026-08-04 04:05:43 | 12.126 |
| update | {'FINISHED': 1} | 2026-08-04 04:05:43 | 2026-08-04 04:05:52 | 9.066 |
| report | {'FINISHED': 2} | 2026-08-04 04:05:58 | 2026-08-04 04:06:44 | 0.000 |
| agent_shutdown | {'FINISHED': 1} | 2026-08-04 04:06:44 | 2026-08-04 04:06:44 | 0.000 |

### Interpretation & Insights
- Slowest activities: `conduct_simulation_campaign` (141.152s), `simulate` (120.786s), `critique` (12.126s), `update` (9.066s), `plan` (8.864s)
- Fastest activities: `agent_startup` (0.000s), `agent_shutdown` (0.000s), `report` (0.000s)
- Timing outliers (IQR rule): `conduct_simulation_campaign` (141.152s), `simulate` (120.786s)

## Per Activity Details
- **conduct_simulation_campaign** (`n=2`, subtype=`academy_loop`)
- **agent_startup** (subtype=`academy_lifecycle`)
- **plan** (subtype=`langgraph_node`)
  - Used:
    - `inputs`: `SearchState(seed='CNC(N)=O', plan='', tool_calls=[], simulated_molecules={}, conclusions=[], critique='')`
  - Generated:
    - `outputs`: `SearchState(seed='CNC(N)=O', plan="The molecule CNC(N)=O (cyanamide oxide) is an interesting starting point for exploring high ionization...`
- **gpt-4o-2024-11-20** (`n=6`, subtype=`llm_call`)
  - Used (aggregated):
    - `messages`: presence=100.0%; type=mixed; sample=[['You are a expert computational chemist tasked with finding molecules with ...
    - `model`: presence=100.0%; type=scalar/categorical; top_values=gpt4o (6)
  - Generated (aggregated):
    - `completion_tokens`: presence=100.0%; type=scalar/categorical; top_values=REDACTED (6)
    - `model`: presence=100.0%; type=scalar/categorical; top_values=gpt-4o-2024-11-20 (6)
    - `prompt_tokens`: presence=100.0%; type=scalar/categorical; top_values=REDACTED (6)
    - `text`: presence=100.0%; type=scalar/categorical; top_values= (2), The molecule CNC(N)=O (cyanamide oxid... (1), ### New Conclusions Based on Simulati... (1)
    - `total_tokens`: presence=100.0%; type=scalar/categorical; top_values=REDACTED (6)
- **tool_calling** (`n=2`, subtype=`langgraph_node`)
  - Used (aggregated):
    - `inputs`: presence=100.0%; type=scalar/categorical; top_values=SearchState(seed='CNC(N)=O', plan="Th... (1), SearchState(seed='CNC(N)=O', plan='##... (1)
  - Generated (aggregated):
    - `outputs`: presence=100.0%; type=scalar/categorical; top_values=SearchState(seed='CNC(N)=O', plan="Th... (1), SearchState(seed='CNC(N)=O', plan='##... (1)
- **simulate** (`n=2`, subtype=`langgraph_node`)
  - Used (aggregated):
    - `inputs`: presence=100.0%; type=scalar/categorical; top_values=SearchState(seed='CNC(N)=O', plan="Th... (1), SearchState(seed='CNC(N)=O', plan='##... (1)
  - Generated (aggregated):
    - `outputs`: presence=50.0%; type=scalar/categorical; top_values=SearchState(seed='CNC(N)=O', plan="Th... (1)
- **compute_ionization_energy** (`n=10`, subtype=`tool_call`)
  - Used (aggregated):
    - `input`: presence=100.0%; type=scalar/categorical; top_values={'smiles': 'CF3NC(N)=O'} (1), {'smiles': 'C6H5NC(N)=O'} (1), {'smiles': 'CNC(N)=F'} (1)
  - Generated (aggregated):
    - `output`: presence=20.0%; type=numeric; min=13.198; p50=13.657; p95=14.070; max=14.116
- **conclude** (subtype=`langgraph_node`)
  - Used:
    - `inputs`: `SearchState(seed='CNC(N)=O', plan="The molecule CNC(N)=O (cyanamide oxide) is an interesting starting point for exploring high ionization...`
  - Generated:
    - `outputs`: `SearchState(seed='CNC(N)=O', plan="### New Conclusions Based on Simulation Results:\n\n1. **Invalid SMILES strings caused simulation fail...`
- **should_continue** (subtype=`langgraph_node`)
  - Used:
    - `inputs`: `SearchState(seed='CNC(N)=O', plan="### New Conclusions Based on Simulation Results:\n\n1. **Invalid SMILES strings caused simulation fail...`
  - Generated:
    - `outputs`: `critique`
- **critique** (subtype=`langgraph_node`)
  - Used:
    - `inputs`: `SearchState(seed='CNC(N)=O', plan="### New Conclusions Based on Simulation Results:\n\n1. **Invalid SMILES strings caused simulation fail...`
  - Generated:
    - `outputs`: `SearchState(seed='CNC(N)=O', plan="### New Conclusions Based on Simulation Results:\n\n1. **Invalid SMILES strings caused simulation fail...`
- **update** (subtype=`langgraph_node`)
  - Used:
    - `inputs`: `SearchState(seed='CNC(N)=O', plan="### New Conclusions Based on Simulation Results:\n\n1. **Invalid SMILES strings caused simulation fail...`
  - Generated:
    - `outputs`: `SearchState(seed='CNC(N)=O', plan='### Updated Plan for Ionization Energy Exploration Campaign\n\n#### Objectives:\n1. Correct and valida...`
- **report** (`n=2`, subtype=`academy_action`)
  - Used (aggregated):
    - `args`: presence=100.0%; type=mixed; sample=[]
- **agent_shutdown** (subtype=`academy_lifecycle`)

### Interpretation & Insights
- Activities with richest **used** metadata: `gpt-4o-2024-11-20` (2 fields), `plan` (1 fields), `tool_calling` (1 fields)
- Activities with richest **generated** metadata: `gpt-4o-2024-11-20` (5 fields), `plan` (1 fields), `tool_calling` (1 fields)
- Highest numeric variability fields: `compute_ionization_energy:generated.output` (range=0.918)

## Workflow-level Resource Usage
| Metric | Value |
| --- | --- |
| Telemetry Samples (task start/end pairs) | 29 |
| CPU User Time Delta | 5737.450 |
| CPU System Time Delta | 271.790 |
| Average CPU (%) Delta | 19.5% |
| Average CPU Frequency | 981 |
| Memory Used Delta | 1.42 GB |
| Average Memory (%) | 60.7% |
| Average Swap (%) | 98.9% |
| Disk Read Time Delta (ms) | 0.000 |
| Disk Write Time Delta (ms) | 0.000 |
| Disk Busy Time Delta (ms) | 0.000 |

### Interpretation & Insights
- CPU-heavy period (avg delta): `19.5%`.
- Memory pressure (delta): `1.42 GB`; peak RSS: `-`.
- Process-level pressure: cpu_user_delta=`0.000`, cpu_system_delta=`0.000`.

## Per-activity Resource Usage
| Activity | Elapsed (s) | CPU User (s) | CPU System (s) | CPU (%) | Memory Delta |
| --- | --- | --- | --- | --- | --- |
| conduct_simulation_campaign | 141.152 | 0.000 | 0.000 | - | - |
| agent_startup | 0.000 | 0.000 | 0.000 | - | - |
| plan | 8.864 | 10.020 | 3.980 | 2.0% | - |
| gpt-4o-2024-11-20 | 6.309 | 96.310 | 22.650 | 6.1% | 685.36 MB |
| tool_calling | 1.516 | 19.100 | 3.370 | 35.8% | 38.24 MB |
| simulate | 120.786 | 0.830 | 0.770 | 6.2% | 77.36 MB |
| compute_ionization_energy | 0.418 | 5543.040 | 225.560 | 53.2% | - |
| conclude | 3.792 | 3.650 | 1.450 | 0.5% | 34.50 MB |
| should_continue | 0.008 | 0.010 | 0.000 | - | - |
| critique | 12.126 | 29.510 | 7.510 | 1.1% | 372.17 MB |
| update | 9.066 | 34.350 | 6.470 | 8.8% | 241.16 MB |
| report | 0.000 | 0.630 | 0.030 | 32.4% | 876.00 KB |
| agent_shutdown | 0.000 | 0.000 | 0.000 | - | - |

### Interpretation & Insights
- Most CPU-active Activities:
  - `compute_ionization_energy`: CPU=53.2%
  - `tool_calling`: CPU=35.8%
  - `report`: CPU=32.4%
  - `update`: CPU=8.8%
  - `simulate`: CPU=6.2%
- Largest memory growth Activities:
  - `gpt-4o-2024-11-20`: Memory Delta=685.36 MB
  - `critique`: Memory Delta=372.17 MB
  - `update`: Memory Delta=241.16 MB
  - `simulate`: Memory Delta=77.36 MB
  - `tool_calling`: Memory Delta=38.24 MB

## Aggregation Method
- Grouping key: `activity_id`.
- Each grouped row may aggregate multiple task records (`n_tasks`).
- Aggregated metrics currently include count/status/timing.

---
Provenance card generated by [Flowcept](https://flowcept.org/) | [GitHub](https://github.com/ORNL/flowcept) | [Version: 0.10.2](https://github.com/ORNL/flowcept/releases/tag/v0.10.2) on Aug 03, 2026 at 11:09 PM CDT
