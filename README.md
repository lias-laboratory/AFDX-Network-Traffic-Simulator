# An Open-Source Configurable Scenario Generator for Real-Time Ethernet Networks


## Description

This AFDX Simulator is the open-source implementation of the configurable scenario generator for real-time Ethernet networks described in *"An Open-Source Configurable Scenario Generator for Real-Time Ethernet Networks"* (Halabi, Guidolin--Pina, Ridouard). It is a tool for generating AFDX (Avionics Full-Duplex Switched Ethernet) network traffic. It allows users to generate reproducible network configurations with different topologies and data flows, and implements admission control to manage link load with automatic routing, so that timing analysis methods can be evaluated, compared, and stress-tested on identical scenarios.


# Cite this project
This repo is the official implementation of *"An Open-Source Configurable Scenario Generator for Real-Time Ethernet Networks"* (Zakarya Halabi, Damien Guidolin--Pina, Frédéric Ridouard). To cite this project, please use the following information:
 
```
@misc{halabi2026afdxgenerator,
      title={An Open-Source Configurable Scenario Generator for Real-Time Ethernet Networks},
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
  - `ring`: Ring topology (minimum 4 switches required)
  - `random`: Random topology based on a spanning tree

- **AFDX flow generation**:
  - Configurable parameters (packet size, BAG, priority)
  - Admission control based on port capacity
  - Automatic shortest-path routing (BFS)

- **JSON export**:
  - Full configuration snapshot (switches, end systems)
  - Details of admitted and rejected flows
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
|           Option            |              Description              |                        Possible values                    |           Default           |
| --------------------------- | --------------------------------------| ----------------------------------------------------------| --------------------------- |
| -T, --topology              | Network topology type                 | single_node,line1I/1N,lineNI/1O,lineNI/NO,tree,ring,random| **single_node**             |
| -Nsw, --nb_switch           | Number of switches                    | Entier > 0                                                | **1**                       |
| -Nes, --nb_end_system       | Number of end systems to generate     | Entier > 0                                                | **3 * nb-switch**           |
| -Nfl, --nb_flux             | Number of flows                       | Entier > 0                                                | **3 * nb-switch**           |
| -L, --size                  | Packet size interval (bytes)          | "Lmin - Lmax"                                             | **"64-1518"**               |
| -BAG, --bag                 | BAG interval (µs)                     | "BAG min - BAG max"                                       | **"128-16384"**             |
| -C, --capacity_port         | Capacity of each output port (Mbps)   | Entier > 0                                                | **"100 (Mbps) "**           |
| -Policy,--policy_service    | Service policy                        | **FIFO,FP/FIFO**                                          | **FIFO**                    |
| -Se,--seed                  | Random seed                           | Integer                                                   | **System clock**            |
| -O, --output                | JSON output file                      | Path                                                      | **Generator_Output.json**   |


### Usage examples
1.Single-switch topology:
```bash
python3 generateur.py --topology single_node --nb_switch 1 --nb_end_system 3 --nb-flux 7 --size 100-1000 --bag 128-4096 --seed 42
```  
2.Line topology with 3 switches:
```bash
python3 generateur.py --topology line1I/1O --nb_switch 3 --nb_flux 15 --size 100-1000 --bag 128-4096
```

3.Ring topology:
```bash
python3 generateur.py --topology ring --nb_switch 4 --nb_flux 20
```

4.Random topology with custom output file:
```bash
python3 generateur.py --topology random --nb_switch 5 --nb_flux 30 --seed 12345 --output results_random.json
```
5.Custom port capacity and explicit end system count:
```bash
python3 generateur.py --topology lineNI/1O --nb_switch 4 --nb_End_System 12 --nb_flux 40 --capacity_port 1000
```

### Complete example (all options)
```bash
python3 generateur.py \
  -T lineNI/NO \
  -Nsw 4 \
  -Nes 10 \
  -Nfl 25 \
  -L 100-1200 \
  -BAG 128-8192 \
  -C 100 \
  -Policy FP/FIFO \
  -Se 42 \
  -O scenario_line.json
```


## JSON Output Structure
```json
{
  "metadata": {
    "nb_Flux": 15,
    "nb_Switches": 3,
    "nb_End_System": 8,
    "nom_topologie": "line1I/1O"
  },
  "end_systems": [
    {
      "id": "ES1",
      "port_sortie": {
        "id": "ES1_OUT_0",
        "destination": "SW1",
        "debit_Mbps": 100
      }
    }
  ],
  "switches": [
    {
      "id": "SW1",
      "port_entree": ["ES1", "ES2"],
      "port_sortie": [
        {
          "id": "SW1_OUT_to_SW2",
          "destination": "SW2",
          "debit_Mbps": 100,
          "charge_Mbps": 45.6,
          "charge_porsentage": 45.6
        }
      ]
    }
  ],
  "Flux": [
    {
      "id": "V1",
      "source": "ES1",
      "destination": "ES4",
      "taille_bytes": 512,
      "priorite": 2,
      "bag_us": 1024,
      "chemin": ["ES1", "SW1", "SW2", "ES4"]
    }
  ],
  "Flux_refuser": [
    {
      "id": "V3",
      "source": "ES2",
      "destination": "ES4",
      "chemin": "REJETÉ"
    }
  ]
}
```
## Code Architecture
### Main class
**`generateur`**: The main class orchestrating the generation.Its constructor takes the seed, topology name, switch count, end-system count, flow count, packet size range, BAG range, service policy, and port capacity.

Topology construction:

- `generer_topologie()`: Builds **only the switches and inter-switch links** (no end systems, no flows) according to `nom_topologie`; returns the list of `Switch`
- `arbre_couvrant_prufer(n)`: Builds a random uniform spanning tree over `n` switches via a Prüfer sequence (used by the `random` topology)
- `aretes_supplementaires(n, aretes_exist, k)`: Draws `k` extra switch-to-switch edges not already in the spanning tree, to introduce cycles (used by the `random` topology)
- `generer_end_systems(switches)`: Creates the `ES1..ES{Nes}` end systems and attaches them to the appropriate switch, following rules specific to each topology

Flow generation and routing:
- `generer_flux(end_systems)`: Creates `Flow` objects (id, source, destination only — no size/BAG/priority yet) by drawing valid source/destination pairs according to the topology's rules
- `dess_graph(switches, end_systems, oriente=False)`: Builds the network graph used for routing
- `courte_chemin(graphe, src, dst)`: Finds the shortest path between two nodes using BFS
- `routage(switches, end_systems, flows)`: Computes and assigns the path of each flow by calling `courte_chemin`
- `load_Calculation(switches, flows)`: Builds, per output port, the list of flow IDs that traverse it 
Admission control and cleanup:
- `controle_admission(switches, flows, interference)`: For each flow, draws frame size, BAG, and (if `FP/FIFO`) priority and admits the flow only if it fits the capacity of every port on its path; also computes and stores the final `charge_mbps` / `charge_porcentage` on each `Output_port`. Rejected flows get `chemin = "REJETE"`
- `elaguer_end_systems(end_systems, switches, flux_admis)`: Removes end systems that are neither a source nor a destination of any admitted flow
- `generer()`: Main entry point; chains all the steps above and returns a `configuration` object

### Module-level export function
- `sauvegarder_resultat(configuration, nom_fichier)`: Serializes the `configuration` object to JSON in the format described above

### Admission control
The simulator implements admission control based on:
 
- Port capacity: 100 Mbps by default (configurable via `-C, --capacity_port`)
- Verification of inter-switch link loads (cumulative)
- Per-flow bandwidth calculation: `(taille_bytes × 8) / bag_us` (Mbps)
For each flow, up to `max_essais_admission` attempts (10 by default) are made, redrawing the frame size, BAG, and priority each time. Flows for which no valid draw fits within the capacity of every port on their path are marked `"REJETE"` and recorded in `Flux_refuser`. End systems that end up neither a source nor a destination of any admitted flow are pruned from the final configuration.


## Constraints

- The `ring` topology requires at least 4 switches (`--nb-switch ≥ 4`)
- The `tree` topology requires at least 3 switches (`--nb-switch ≥ 3`)
- BAG values are restricted to powers of 2 within the specified interval
- Each port capacity is fixed at 100 Mbps by default, and can be changed with `-C, --capacity_port`
- The `modele.py` module must be present in the same directory


## Project Structure

The project consists of two main files:

- `generateur.py`: Generation logic, topology builders, routing, and JSON export
- `modele.py`: Data class definitions (`Flow`, `Switch`, `End_System`, `Output_port`, `configuration`)

## License
This project is licensed under the MIT License. See [LICENSE](LICENSE) for more details.

## Contributors
- Zakarya Halabi, Sorbonne University, Paris, France
- Damien GUIDOLIN--PINA, LyRIDS, ECE Engineering School, OMNES Education, Paris, France
- [Frédéric RIDOUARD](https://www.lias-lab.fr/fr/members/fredericridouard/),  LIAS, ISAE-ENSMA, France