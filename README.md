# Automatic Configuration Generation for Real-Time Ethernet Networks


## Description

This AFDX Simulator is the open-source implementation of the configurable scenario generator for real-time Ethernet networks described in *"Automatic Configuration Generation for Real-Time Ethernet Networks"*. It is a tool for generating AFDX (Avionics Full-Duplex Switched Ethernet) network traffic. It allows users to generate reproducible network configurations with different topologies and data flows, and implements admission control to manage link load with automatic routing, so that timing analysis methods can be evaluated, compared, and stress-tested on identical scenarios.


# Cite this project
This repo is the official implementation of *"An Open-Source Configurable Scenario Generator for Real-Time Ethernet Networks"* (Zakarya Halabi, Damien Guidolin--Pina, Frédéric Ridouard). To cite this project, please use the following information:
 
```
@misc{halabi2026afdxgenerator,
      title={Automatic Configuration Generation for Real-Time Ethernet Networks},
      author={Zakarya Halabi and Damien Guidolin--Pina and Frédéric Ridouard},
      year={2026},
      howpublished={\url{https://forge.lias-lab.fr/afdx-network-traffic-simulator}}
}
```

## Features

- **Network topology generation**:
  - `single_node`: A single switch with multiple sources and one destination
  - `line1I/1O`: Multiple switches in a line, with all sources connected to the first switch and a single destination at the last
  - `lineNI/1O`: Multiple switches in a line, with sources distributed evenly across switches and a single destination
  - `lineNI/NO`: Multiple switches in a line, with multiple sources and multiple destinations
  - `tree`: Complete binary tree (minimum 3 switches required)
  - `ring`: Ring topology (minimum 3 switches required)
  - `random`: Random topology based on a spanning tree

- **AFDX flow generation**:
  - Configurable parameters (packet size, BAG, priority)
  - Admission control based on port bandwidth
  - Automatic shortest-path routing (BFS)

- **JSON export**:
  - Full configuration snapshot (switches, end systems)
  - Details of admitted flows
  - Computed port load values




## Prerequisites

- Python 3.8 or higher
- Module `modele.py` (classes `Flow`, `Switch`, `End_System`, `Output_port`, `configuration`)

## Installation

Clone the repository:

```bash
git clone https://github.com/lias-laboratory/AFDX-Network-Traffic-Simulator
cd AFDX-Network-Traffic-Simulator 
```


## Utilisation

### Basic syntax
```bash
python3 generateur.py [options]
```
### Options
|           Option            |              Description              |                        Possible values                     |           Default           |
| --------------------------- | --------------------------------------| -----------------------------------------------------------| --------------------------- |
| -T, --topology              | Network topology type                 | single_node,line1I/1O,lineNI/1O,lineNI/NO,tree,ring,random | **single_node**             |
| -Nsw, --nb_switch           | Number of switches                    | Entier > 0                                                 | **1**                       |
| -Nes, --nb_end_system       | Number of end systems to generate     | Entier > 0                                                 | **3 * nb_switch**           |
| -Nfl, --nb_flow             | Number of flows                       | Entier > 0                                                 | **3 * nb_switch**           |
| -L, --size                  | Packet size interval (bytes)          | "Lmin - Lmax"                                              | **"64-1518"**               |
| -BAG, --bag                 | BAG interval (µs)                     | "BAG min - BAG max"  (**both bounds must be powers of 2**) | **"128-16384"**             |
| -R, --bandwidth_port        | bandwidth of each output port (Mbps)  | Entier > 0                                                 | **"100 (Mbps) "**           |
| -Policy,--policy_service    | Service policy                        | **FIFO,FP/FIFO**                                           | **FIFO**                    |
| -Pm,--priority_max          | Number of priority Maximum            | Entier > 0                                                 | **4**                    |
| -Se,--seed                  | Random seed                           | Integer                                                    | **System clock**            |
| -O, --output                | Output file                           | Path                                                       | **Generator_Output.json**   |


### Usage examples
1.Single switch topology:
```bash
python3 generator.py --topology single_node --nb_switch 1 --nb_end_system 3 --nb_flow 7 --size 100-1000 --bag 128-16384 --seed 42
```  
2.Line topology with 3 switches:
```bash
python3 generator.py --topology line1I/1O --nb_switch 3 --nb_flow 15 --size 100-1000 --bag 128-4096
```

3.Ring topology:
```bash
python3 generator.py --topology ring --nb_switch 4 --nb_flow 20
```

4.Random topology with custom output file:
```bash
python3 generator.py --topology random --nb_switch 5 --nb_flow 30 --seed 12345 --output results_random.json
```
5.Custom port capacity and explicit end system count:
```bash
python3 generator.py --topology lineNI/1O --nb_switch 4 --nb_end_system 12 --nb_flow 40 --bandwidth_port 1000
```

### Complete example (all options)
```bash
python3 generator.py \
  -T lineNI/NO \
  -Nsw 4 \
  -Nes 10 \
  -Nfl 25 \
  -L 100-1200 \
  -BAG 128-8192 \
  -R 100 \
  -Policy FP/FIFO \
  -Pm 5 \
  -Se 42 \
  -O scenario_line.json
```


## JSON Output Structure
```json
{
  "metadata": {
    "nb_Flow": 15,
    "nb_Switches": 3,
    "nb_End_System": 8,
    "topology": "line1I/1O"
  },
  "end_systems": [
    {
      "id": "ES1",
      "output_port": {
         "id": "ES1_OUT_0",
         "destination": "SW1",
         "bandwidth": 100
      }
    }
  ],
  "switches": [
    {
      "id": "SW1",
      "input_port": ["ES1", "ES2"],
      "output_port": [
        {
          "id": "SW1_OUT_to_SW2",
          "destination": "SW2",
          "bandwidth": 100,
          "load_mbps": 45.6,
          "load_percentage": 45.6
        }
      ]
    }
  ],
  "Flow": [
    {
      "id": "V1",
      "source": "ES1",
      "destination": "ES4",
      "size": 512,
      "priority": 2,
      "bag": 1024,
      "path": ["ES1", "SW1", "SW2", "ES4"]
    }
  ],
}
```
## Code Architecture
### Main class
**`generator`**: The main class orchestrating the generation. Its constructor takes the seed, topology name, switch count, end-system count, flow count, size range, BAG range, service policy, priority maximum (if `FP/FIFO`) and port bandwidth.

Topology construction:

- `topology_generation()`: Builds **only the switches and inter-switch links** according to `topology`,then calls `generate_end_systems(switches)` to create and attach the end systems; returns the list of `Switch` and the list of `End_System` objects 
- `prufer_spanning_tree(n)`: Builds a random uniform spanning tree over `n` switches via a Prüfer sequence (used by the `random` topology)
- `additional_edges(self, n, aretes_exist, k)`: Draws `k` extra switch-to-switch edges not already in the spanning tree, to introduce cycles (used by the `random` topology)
- `generate_end_systems(switches)`: Creates the `ES1..ES{Nes}` end systems and attaches them to the appropriate switch, following rules specific to each topology

Flow generation and routing:

- `generate_flows(end_systems)`: Creates `Flow` objects (id, source, destination only — no size/BAG/priority yet) by drawing valid source/destination pairs according to the topology's rules
- `dess_graph(switches, end_systems)`: Builds the network graph used for routing
- `short_path(graph, src, dst)`: Finds the shortest path between two nodes using BFS
- `routage(switches, end_systems, flows)`: Computes and assigns the path of each flow by calling `courte_chemin`
- `load_Calculation(switches, flows)`: Builds, per output port, the list of flow IDs that traverse it 

Admission control and cleanup:

- `check_admit(ports_id, interference, rho_min)`: Pre-check run before admission control; verifies that no output port is structurally not admit even under the best-case minimum load (`N_j * rho_min <= R_j`), and raises with a detailed `[ERROR]` message per offending port if not

- `controle_admission(switches, flows, interference)`: For each flow, draws frame size, BAG, and (if `FP/FIFO`) priority, and admits the flow only if it fits the capacity of every port on its path; also computes and stores the final `load_mbps` / `load_porcentage` on each `Output_port`
- `generer()`: Main entry point; chains all the steps above and returns a `configuration` object

### Module-level export function
- `sauvegarder_resultat(configuration, nom_fichier)`: Serializes the `configuration` object to JSON in the format described above

### Admission control
The simulator implements admission control based on:
 
- Port capacity: 100 Mbps by default (configurable via `-R, --bandwidth_port`)
- Verification of inter-switch link loads (cumulative)
- Per-flow bandwidth calculation: `(size × 8) / bag` (Mbps)

Unlike a trial-and-error scheme, the algorithm is **deterministic and rejection-free by construction**: for each flow, the frame size is drawn from a range that is bounded *in advance* so that a valid BAG always exists for the remaining port capacity (`rho_min = Lmin × 8 / BAGmax` is the lowest achievable rate, so as long as the available capacity stays above `rho_min` a solution is guaranteed). Output ports are processed in decreasing order of the number of flows they carry.
 
As a result, in the current implementation no admitted flow is ever rejected for capacity reasons once admission control starts; a hard `[ERROR]` / exception is raised *before* admission control begins instead, if the current `-L` / `-BAG` / `-R` combination makes at least one port infeasible even in the best case (see `check_admit`). A flow can also be absent from the final set if no path exists between its source and destination in the topology (BFS routing failure).




## Constraints

- The `tree`, `ring`, and `random` topologies each require at least 3 switches (`-Nsw ≥ 3`); if you pass fewer, the generator automatically downgrades to a compatible topology (`single_node` for `-Nsw=1`, `line1I/1O` for `-Nsw=2`) and prints a `[WARNING]`.
- Bvalues must be powers of 2 within the specified range. For each flow, the BAG is selected from `{128, 256, 512, ...}` between `BAGmin` et  `BAGmax<`. If the `-BAG` limits are not powers of 2, they are automatically adjusted to the nearest valid values.
-The default port capacity is 100 Mbps. It can be changed using `-R, --bandwidth_port`.
- `-Pm, --priority_max` option is used only with `-Policy=FP/FIFO`.A non-zero value with `-Policy=FIFO` is a validation error.
- The `modele.py` module must be present in the same directory.



## Project Structure

The project consists of two main files:

- `generateur.py`: Generation logic, topology builders, routing, and JSON export
- `modele.py`: Data class definitions (`Flow`, `Switch`, `End_System`, `Output_port`, `configuration`)

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for more details.

## Contributors
- Zakarya HALABI, Sorbonne University, Paris, France
- Damien GUIDOLIN--PINA, LyRIDS, ECE Engineering School, OMNES Education, Paris, France
- [Frédéric RIDOUARD](https://www.lias-lab.fr/fr/members/fredericridouard/),  LIAS, ISAE-ENSMA, France