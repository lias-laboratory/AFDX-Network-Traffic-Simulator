# AFDX Simulator - Traffic Generator and Network Topologies


## Description

This AFDX Simulator is a tool for generating AFDX (Avionics Full-Duplex Switched Ethernet) network traffic. It allows users to generate network configurations with different topologies and data flows, and implements admission control to manage link load with automatic routing.

## Features

- **Network topology generation**:
  - `single_node`: A single switch with multiple sources and one destination
  - `line1`: Multiple switches in a line, with all sources connected to the first switch and a single destination at the last
  - `line2`: Multiple switches in a line, with sources distributed evenly across switches and a single destination
  - `line3`: Multiple switches in a line, with multiple sources and multiple destinations
  - `join`: Complete binary tree (minimum 3 switches required)
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
git clone https://git.lias-lab.fr/halabiz/afdx_network_traffic_simulator.git
cd afdx_network_traffic_simulator 
```


## Utilisation

### Basic syntax
```bash
python3 generateur.py [options]
```
### Options
|           Option            |              Description              |                 Possible values               |           Default           |
| --------------------------- | --------------------------------------| ----------------------------------------------| --------------------------- |
| -topo, --topology           | Network topology type                 | single_node,line1,line2,line3,join,ring,random| **single_node**             |
| -nbsw, --nb-switch          | Number of switches                    | Entier > 0                                    | **1**                       |
| -nbfl, --nb-flux            | Flow count interval                   | "min - max" ou "valeur"                       | **3 * nb_switch**           |
| -s, --size                  | Packet size interval (bytes)          | "min - max"                                   | **"64-1518"**               |
| -bg, --bag                  | BAG interval (µs)                     | "min - max"                                   | **"128-16384"**             |
| -nbes, --nb_End_System      | Number of end systems to generate     | Entier > 0                                    | **3 * nb_switch**           |
| -cap, --Capacity_port       | Capacity of each output port (Mbps)   | Entier > 0                                    | **"100.0 (Mbps) "**         |
| -policy,--service-policy    | Service policy                        | **FIFO,FP/FIFO**                              | **FIFO**                    |
| --seed                      | Random seed                           | Integer                                       | **System clock**            |
| -o, --output                | JSON output file                      | Path                                          | **Generator_Output.json**   |


### Usage examples
1.Single-switch topology:
```bash
python3 generateur.py --topology single_node --nb-switch 1 --nb-flux 5-10 --seed 42
```  

2.Line topology with 3 switches:
```bash
python3 generateur.py --topology line1 --nb-switch 3 --nb-flux 10-20 --size 100-1000 --bag 128-4096
```

3.Ring topology:
```bash
python3 generateur.py --topology ring --nb-switch 4 --nb-flux 15-30
```

4.Random topology with custom output file:
```bash
python3 generateur.py --topology random --nb-switch 5 --nb-flux 20-50 --seed 12345 -o results_random.json
```
5.Custom port capacity and explicit end system count:
```bash
python3 generateur.py --topology line2 --nb-switch 4 --nb_End_System 12 --nb-flux 30-60 --capacity_port 1000
```
## JSON Output Structure
```json
{
  "metadata": {
    "nb_Flux": 15,
    "nb_Switches": 3,
    "nb_End_System": 8,
    "nom_topologie": "line1"
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
**`generateur`**: The main class orchestrating the generation.Its constructor takes the seed, flow count range, service policy, packet size range, BAG range, end-system count, topology name, switch count, max priority, max admission attempts, and port capacity.

Topology construction:
opology construction:
- `generer_topologie()`: Builds **only the switches and inter-switch links** (no end systems, no flows) according to `nom_topologie`; returns the list of `Switch`
- `arbre_couvrant_prufer(n)`: Builds a random uniform spanning tree over `n` switches via a Prüfer sequence (used by the `random` topology)
- `aretes_supplementaires(n, aretes_exist, k)`: Draws `k` extra switch-to-switch edges not already in the spanning tree, to introduce cycles (used by the `random` topology)
- `generer_end_systems(switches)`: Creates the `ES1..ES{nb_es}` end systems and attaches them to the appropriate switch, following rules specific to each topology

Flow generation and routing:
- `generer_flux(end_systems)`: Creates `Flow` objects (id, source, destination only — no size/BAG/priority yet) by drawing valid source/destination pairs according to the topology's rules
- `dess_graph(switches, end_systems, oriente=False)`: Builds the network graph used for routing
- `courte_chemin(graphe, src, dst)`: Finds the shortest path between two nodes using BFS
- `routage(switches, end_systems, flows)`: Computes and assigns the path of each flow by calling `courte_chemin`
- `load_Calculation(switches, flows)`: Builds, per output port, the list of flow IDs that traverse it 
Admission control and cleanup:
- `controle_admission(switches, flows, interference)`: For each flow, draws frame size, BAG, and (if `FP/FIFO`) priority — up to `max_essais_admission` times — and admits the flow only if it fits the capacity of every port on its path; also computes and stores the final `charge_mbps` / `charge_porcentage` on each `Output_port`. Rejected flows get `chemin = "REJETE"`
- `elaguer_end_systems(end_systems, switches, flux_admis)`: Removes end systems that are neither a source nor a destination of any admitted flow
- `generer()`: Main entry point; chains all the steps above and returns a `configuration` object

### Module-level export function
- `sauvegarder_resultat(configuration, nom_fichier)`: Serializes the `configuration` object to JSON in the format described above

### Admission control
The simulator implements admission control based on:
 
- Port capacity: 100 Mbps by default (configurable via `-cap, --capacity-port`)
- Verification of inter-switch link loads (cumulative)
- Per-flow bandwidth calculation: `(taille_bytes × 8) / bag_us` (Mbps)
For each flow, up to `max_essais_admission` attempts (10 by default) are made, redrawing the frame size, BAG, and priority each time. Flows for which no valid draw fits within the capacity of every port on their path are marked `"REJETE"` and recorded in `Flux_refuser`. End systems that end up neither a source nor a destination of any admitted flow are pruned from the final configuration.


## Constraints

- The `ring` topology requires at least 4 switches (`--nb-switch ≥ 4`)
- The `join` topology requires at least 3 switches (`--nb-switch ≥ 3`)
- BAG values are restricted to powers of 2 within the specified interval
- Each port capacity is fixed at 100 Mbps by default, and can be changed with `-cap, --capacity-port`
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