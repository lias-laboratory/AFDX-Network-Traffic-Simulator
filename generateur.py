"""
AFDX Traffic Configuration Generator

Generates AFDX network configurations with multiple topologies and traffic flows. 
Implements admission control with bag (Bandwidth Allocation Gap) and frame size allocation for avionics network simulations.

Supported Topologies: single_node, line1I/1O, lineNI/1O, lineNI/NO, tree, ring, random
QoS Policies: FIFO, FP/FIFO

Usage:
    python3 generator.py [-T TOPOLOGY] 
                         [-Nsw SWITCHES] 
                         [-Nes ES] 
                         [-Nfl FLOWS] 
                         [-L SIZE]
                         [-bag bag_RANGE]  
                         [-R BANDWITH_PORT] 
                         [-policy policy_service] 
                         [-Pm Priority_Max ] 
                         [-O OUTPUT]


Example:
    python3 generator.py --topology tree --nb_switch 7 --nb_end_system 20 --nb_flow 15 --seed 40
    python3 generator.py  -T tree  -Nsw 7 -Nes 20 -Nfl 15 -Se 40


Requirements: 
    modele.py : Contains the data models (Switch, End_System, Flow, Output_port, configuration)
    Python 3.7+
    

Author: Zakarya Halabi (Zakarya.Halabi@etu.sorbonne-universite.fr / zakarya.halabi@ensma.fr )
Affiliation: LIAS Laboratory, ISAE-ENSMA
Date: JULY 2026
"""
import argparse
from collections import deque
import heapq
import json
import math
import random
import sys
import time
from typing import Dict, List, Optional, Set
from modele import *

# function to create a bag in powers of 2.
def bag_us(first, last):
    """
    Returns the bags (in µs) of the form 2^k, with:
        k_min = ceil(log2(start))
        k_max = floor(log2(end))
    so all 2^k within [start, end]

   
    """
    if first <= 0 or last < first:
        return []

    k_min = math.ceil(math.log2(first))
    k_max = math.floor(math.log2(last))

    return [2 ** k for k in range(k_min, k_max + 1)]


class generator:
    """
    Generates network topologies and communication flows for simulation.
    Parameters:
        seed               : The seed controls the entire randomness of the generator
        nb_flow            : number of flows to generate (default: 3 * nb_switch)
        policy_service     : "FIFO" or "FP/FIFO"
        Size               : (min, max) Ethernet frame size in bytes, constrained to the range [64, 1518]
        bag_range          : (min, max) bag in microseconds, sampled from powers of 2
        topology           : "single_node","line1I/1O","lineNI/1O","lineNI/NO","tree","ring","random"
        nb_switch          : number of Switches (default:1)
        nb_es              : number of end systems (default: 3 * nb_switch)
        bandwidth_port     : output port Bandwidth (rate)
        priority_max       : highest supported priority (0 = highest)
    """

    def __init__(self,seed:int,nb_flow=(int,int),policy_service:str=None,
                 size=(int,int),bag=(int,int),nb_es: Optional[int] = None,topology:str="single_node",
                 nb_switch:int=1,priority_max: int = 4,bandwidth_port:int=100):
        self.seed=seed                                           #Get the seed
        self.rng=random.Random(seed)                             #Create an RNG from a given seed
        #Get the requested number of flows
        if nb_flow is None:
            self.Nfl = 3 * nb_switch
        elif isinstance(nb_flow, int):
            self.Nfl = nb_flow  
        self.policy=policy_service                               #Retrieve the used service policy
        self.size=size                                           #Retrieve the used data size
        self.bag=bag                                             #Get the used bag interval
        self.Nes = nb_es if nb_es is not None else 3 * nb_switch #Get the number of end systems
        self.topology=topology                                   #Get the used topology”
        self.Nsw=nb_switch                                       #Get the used number of switches
        self.priority_max = priority_max                         #Get the maximum priority in use
        self.bandwidth = bandwidth_port                          #Output port bandwidth (Mbps)
      


    #Topology Generation   
    def topology_generation(self):
        """
            Builds only the switches and the links between them (no flows).
            Creates the list ES_1, ..., ES_{N_es} associated with the switches according 
            to the rule imposed by the chosen topology.
            Returns: (switches, end_systems)
        """
        switches=[]             #list for the switches
        end_systems=[]          #list for storing end systems
        n = self.Nsw            #number of switches

        #------ Single Node Topology ----------
        if self.topology == "single_node":
            #Only one switch, no inter-switch links
            switches.append(Switch(id="SW1"))
            #Create and attach end systems to the switches            
            end_systems=self.generate_end_systems(switches)
        
        #------ Line Topologies (1I/1O, NI/1O, NI/NO) --------  
        elif self.topology in ("line1I/1O", "lineNI/1O", "lineNI/NO"):   
            #Create all existing switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))
            #link the switches
            for i in range(1, n):
                #Add the outputs for each switch (name, destination, port throughput)
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{i+1}", 
                        destination=f"SW{(i + 1)}", 
                        bandwidth=self.bandwidth
                        ))
                switches[i].output_port.append(Output_port(
                        id=f"SW{i+1}_OUT_SW{i}",
                        destination=f"SW{i}",
                        bandwidth=self.bandwidth))
               
                #Add the intputs for each switch(name)
                switches[i - 1].intput_port.append(f"SW{i + 1}")
                switches[i].intput_port.append(f"SW{i}")
            
            #Create and attach end systems to the switches
            end_systems=self.generate_end_systems(switches)

        #--------------- Tree Topology ------------------- 
        elif self.topology in ("tree"):
            """
            Binary tree of switches converging on a root switch SW1.
            n must be of the form 2^(h+1) - 1; otherwise, it is rounded up to the next odd number
            """
            n_total = n
            
            #Create all existing switches 
            for i in range(1, n_total + 1):
                switches.append(Switch(id=f"SW{i}"))

            #link the switches
            for i in range(2, n_total + 1):
                parent = i // 2
                #Add the outputs for each switch (name, destination, port throughput)
                switches[parent - 1].output_port.append(Output_port(
                        id=f"SW{parent}_OUT_SW{i}", 
                        destination=f"SW{i}", 
                        bandwidth=self.bandwidth
                        ))
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{parent}", 
                        destination=F"SW{parent}", 
                        bandwidth=self.bandwidth
                        ))
                #Add the intputs for each switch
                switches[parent - 1].intput_port.append(f"SW{i}")
                switches[i - 1].intput_port.append(f"SW{parent}")
            #Store leaf switches for later use
            self._leaves_tree = [f"SW{i}" for i in range(n_total // 2 + 1, n_total + 1)]

            #Create and attach end systems to the switches
            end_systems=self.generate_end_systems(switches)

        
        #--------------- Ring Topology ------------------- 
        elif self.topology in ("ring"):
            """
                Ring topology: SW1 -> SW2 -> ... -> SWn -> SW1
                Each switch connects to its next neighbor in a circular fashion
            """
            #Create all switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))
            #Connect switches in a ring
            for i in range(1, n + 1):
                #Next switch
                suivant = (i % n) + 1
                #Add output port from SWi to its next neighbor
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{suivant}", 
                        destination=f"SW{suivant}", 
                        bandwidth=self.bandwidth
                        ))
                #Add input port to the neighbor
                switches[suivant - 1].intput_port.append(f"SW{i}")

            #Create and attach end systems to the switches
            end_systems=self.generate_end_systems(switches)


        #--------------- Random Topology ------------------- 
        elif self.topology == "random":
            """
                Random spanning tree via a Prüfer sequence, 
                followed by the addition of extra edges to introduce cycles
            """
            #Create all switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))

            #Retrieve the edges created by Prüfer.
            edgess = self.prufer_spanning_tree(n)

            #Total number of links [between n-1 and n(n-1)/2]
            link_min = n - 1 
            link_max = n * (n - 1) // 2

            #randomly generates the number of links created
            nb_link = self.rng.randint(link_min, link_max)

            #Number of links to add to the spanning tree created by Prüfer's method
            k = nb_link - link_min 
            #Add extra edges to create cycles
            edgess |= self.additional_edges(n, edgess, k)

            #Add bidirectional links for each edge
            for (a, b) in edgess:
                #Output port from SWa to SWb
                switches[a - 1].output_port.append(Output_port(
                        id=f"SW{a}_OUT_SW{b}", 
                        destination=f"SW{b}", 
                        bandwidth=self.bandwidth
                        ))
                #Output port from SWb to SWa
                switches[b - 1].output_port.append(Output_port(
                        id=f"SW{b}_OUT_SW{a}", 
                        destination=f"SW{a}", 
                        bandwidth=self.bandwidth
                        ))
                #Input ports
                switches[a - 1].intput_port.append(f"SW{b}")
                switches[b - 1].intput_port.append(f"SW{a}")
            #Create and attach end systems to the switches
            end_systems=self.generate_end_systems(switches)

        else:
            raise ValueError(f"Unknown topology : {self.T}")

        #Return the switches and the end systems
        return switches,end_systems
    
    #Generate spanning tree
    def prufer_spanning_tree(self, n: int) -> set:
        """Constructs a uniform random spanning tree on N switches using a Prüfer sequence"""
        #if we have a single switch
        if n <= 1:
            return set()
        #if we just have two switches,only one possible edge
        if n == 2:
            return {(1, 2)}
        #Generate a random Prüfer sequence of length n-2,Each value is between 1 and n 
        sequence = [self.rng.randint(1, n) for _ in range(n - 2)]
        #Decoding the Prüfer sequence into edges,Initialize degrees: each node starts with degree 1
        degre = [1] * (n + 1)
        for s in sequence:
            degre[s] += 1

        #Set to store the tree edges    
        edges = set()
        #Find all leaves (degree 1)
        leaves = [i for i in range(1, n + 1) if degre[i] == 1]
        #Use a min-heap for deterministic leaf selection
        heapq.heapify(leaves)
        #Process each element of the Prüfer sequence
        for s in sequence:
            #Extract the smallest leaf
            feuille = heapq.heappop(leaves)
            #Sort to ensure consistent ordering
            a, b = tuple(sorted((feuille, s)))
            #Add the edge 
            edges.add((a, b))
            #Decrease degree of the leaf
            degre[feuille] -= 1
            #Decrease degree of the sequence element
            degre[s] -= 1
            #If it becomes a leaf, add it to the heap
            if degre[s] == 1:
                heapq.heappush(leaves, s)
        #Add the final edge 
        lasts = [i for i in range(1, n + 1) if degre[i] == 1]
        #Take the first two remaining leaves
        a, b = tuple(sorted(lasts[:2]))
        edges.add((a, b))
        return edges
    

    
    def additional_edges(self, n: int, edges_exist: set, k: int) -> set:
        """Select exactly k additional edges from among all pairs of switches not already connected by the spanning tree."""
        #Build a list of all possible edges not already in the existing se
        all_possible_pairs = [
            (a, b)
            for a in range(1, n + 1)
            #Only a < b to avoid duplicates
            for b in range(a + 1, n + 1)
            #Exclude existing edges
            if (a, b) not in edges_exist
        ]
        #Limit k to the number of available edges
        k = min(k, len(all_possible_pairs))
        #Randomly select k edges from the available pairs
        return set(self.rng.sample(all_possible_pairs, k))
    
    #End System Generation
    def generate_end_systems(self,switches):
        """
        Create the list ES_1, ..., ES_{N_es} associated with the switches according to the rule imposed by the chosen topology.
        """
        end_systems=[]   #list for storing end systems

        #--------------- Topologies with multiple sources and a single destination ------------------- 
        if self.topology in("single_node","line1I/1O","lineNI/1O"):
            #Retrieve all switches except the last one.       
            if self.topology in ("lineNI/1O","LineNI/1O"):
                switches_source = [switch.id for switch in switches]
            elif len(switches) > 1:
                #line1I/1O:uniquement SW1
                switches_source = [switches[0].id]   
            else:
                #single_node
                switches_source = [switches[0].id]   
            n_dest = 1
            n_src = max(1,self.Nes - n_dest)
            #Create the source end systems and connect them to the switch
            switches_id = {sw.id: sw for sw in switches}
            for i in range(1, n_src + 1):
                idx = (i - 1) % len(switches_source)
                sw_id = switches_source[idx]
                end_systems.append(End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,           
                                bandwidth=self.bandwidth            
                            )))
                #Add ES{i} as an input port of the switch
                switches_id[sw_id].intput_port.append(f"ES{i}")
            #Create the destination end systems and connect them to their switch
            sw_dest_id = switches[-1].id
            end_systems.append(End_System(
                    id=f"ES{n_src + 1}",
                    output_port=Output_port(
                                id=f"ES{n_src + 1}_IN",
                                bandwidth=self.bandwidth
                            )))
            #Add the switch egress port -> destination ES
            for sw in switches:
                if sw.id == sw_dest_id:
                    sw.output_port.append(Output_port(
                            id=f"{sw_dest_id}_OUT_ES{n_src + 1}",
                            destination=f"ES{n_src + 1}",
                            bandwidth=self.bandwidth
                        ))
                    break
        #--------------- Tree Topology ------------------- 
        elif self.topology =="tree":
            leaves = getattr(self, "_leaves_tree", None) or [switches[-1].id]
            nb_leaves = len(leaves)
            n_dest = 1
            n_src = max(1, self.Nes - n_dest)
            switches_id = {sw.id: sw for sw in switches}
            #Create the source end systems and connect them to the switch.
            for i in range(1, n_src + 1):
                idx = (i - 1) % nb_leaves
                sw_id = leaves[idx]
                end_systems.append(End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,           
                                bandwidth=self.bandwidth           
                            )))
                #Add ES{i} as an input port of the switch
                switches_id[sw_id].intput_port.append(f"ES{i}")
            #Create the destination end systems and connect them to their switch
            sw_dest_id = switches[0].id
            end_systems.append(End_System(
                    id=f"ES{n_src + 1}",
                    output_port=Output_port(
                                id=f"ES{n_src + 1}_IN",
                                bandwidth=self.bandwidth
                            )))
            #Add the switch egress port -> destination ES
            switches_id[sw_dest_id].output_port.append(Output_port(
                    id=f"{sw_dest_id}_OUT_ES{n_src + 1}",
                    destination=f"ES{n_src + 1}",
                    bandwidth=self.bandwidth
            ))
        #--------------- lineNI/NO Topology ------------------- 
        elif self.topology =="lineNI/NO":
            #Create the source end systems and connect them to the switch
            switches_id = {sw.id: sw for sw in switches}
            switches_ids = [sw.id for sw in switches]
            nb_sw=len(switches)
            switches_ids_src = switches_ids[:-1] if nb_sw > 1 else switches_ids
            switches_ids_dst = switches_ids[1:] if nb_sw > 1 else switches_ids
            nb_sw_src = len(switches_ids_src)
            nb_sw_dst = len(switches_ids_dst)
            #Two counters for the source and destination end systems.
            c_src = 0
            c_dst = 0
            for i in range(1, self.Nes + 1):
                role = "source" if i % 2 == 1 else "destination"
                #If the role is "source," we do this.
                if role == "source":
                    sw_id = switches_ids_src[c_src % nb_sw_src]
                    c_src += 1
                    es = End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                            id=f"ES{i}_OUT_{sw_id}",
                            destination=sw_id,
                            bandwidth=self.bandwidth
                        ))
                    switches_id[sw_id].intput_port.append(f"ES{i}")
                #If the role is "destination," we do this.
                else:  
                    sw_id = switches_ids_dst[c_dst % nb_sw_dst]
                    c_dst += 1
                    es = End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                            id=f"ES{i}_IN",
                            bandwidth=self.bandwidth
                        ))
                    switches_id[sw_id].output_port.append(Output_port(
                        id=f"{sw_id}_OUT_ES{i}",
                        destination=f"ES{i}",
                        bandwidth=self.bandwidth
                     ))
                  
                es.role = role
                es.sw_id = sw_id   
                end_systems.append(es)
        #--------------- Ring Topology ------------------- 
        elif self.topology == "ring":
            #Distributed in round-robin over the eligible switches
            switches_id = {sw.id: sw for sw in switches}
            switches_ids = [sw.id for sw in switches]
            nb_sw = len(switches)
            c_src = 0
            c_dst = 0
            for i in range(1, self.Nes + 1):
                role = "source" if i % 2 == 1 else "destination"
                if role =="source":
                    sw_id = switches_ids[c_src % nb_sw]
                    c_src += 1
                    es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,
                                bandwidth=self.bandwidth
                        ))
                    #Add ES{i} as an input port of the switch.
                    switches_id[sw_id].intput_port.append(f"ES{i}")
                elif role=="destination":
                    sw_id = switches_ids[c_dst % nb_sw]
                    c_dst += 1
                    es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_IN",
                                bandwidth=self.bandwidth
                        ))
                    #Add the reciprocal output port switch -> ES
                    switches_id[sw_id].output_port.append(Output_port(
                            id=f"{sw_id}_OUT_ES{i}",
                            destination=f"ES{i}",
                            bandwidth=self.bandwidth
                        ))
                es.role = role
                es.sw_id = sw_id
                end_systems.append(es)
        
        #--------------- Random Topology -------------------
        elif self.topology == "random":
                switches_id = {sw.id: sw for sw in switches}
                switches_ids = [sw.id for sw in switches]
        
                def creer_es(i, sw_id, role):
                    if role == "source":
                        es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,
                                bandwidth=self.bandwidth
                            ))
                        switches_id[sw_id].intput_port.append(f"ES{i}")
                    else:
                        es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_IN",
                                bandwidth=self.bandwidth
                        ))
                        switches_id[sw_id].output_port.append(Output_port(
                            id=f"{sw_id}_OUT_ES{i}",
                            destination=f"ES{i}",
                            bandwidth=self.bandwidth
                        ))
                    es.role = role
                    es.sw_id = sw_id
                    return es
        
                #Half source / half destination split over the total Nes
                n_src = (self.Nes + 1) // 2  
                n_dst = self.Nes // 2        
                roles = ["source"] * n_src + ["destination"] * n_dst
                self.rng.shuffle(roles)         
        
                switches_to_cover = switches_ids.copy()
                self.rng.shuffle(switches_to_cover)
        
                i = 1
                for sw_id in switches_to_cover:
                    if i > self.Nes:
                        break
                    role = roles[i - 1]
                    end_systems.append(creer_es(i, sw_id, role))
                    i += 1
        
                for i in range(i, self.Nes + 1):
                    sw_id = self.rng.choice(switches_ids)
                    role = roles[i - 1]
                    end_systems.append(creer_es(i, sw_id, role))
                
        return end_systems


    

    def construct_pairs(self, nb_flow, paires_valides):
        """
        Constructs a list of `nb_flow` (source, destination) pairs from `paires_valides`, ensuring maximum coverage:

            1) Each distinct source is used at least once. 
            2) Each distinct destination not yet covered is then used at least once. 
            3) The remaining budget is filled via standard random selection.
        """
        #List to store the selected (source, destination) pairs
        flow_pairs = []

        #Extract unique sources and destinations from valid pairs
        src_uni = list({s.id: s for (s, d) in paires_valides}.values())
        dst_uni = list({d.id: d for (s, d) in paires_valides}.values())

        #Randomize the order of sources and destinations for diverse selection
        self.rng.shuffle(src_uni)
        self.rng.shuffle(dst_uni)

        #Ensure each distinct source is used at least once
        for es_src in src_uni:
            #Stop if budget is exhausted
            if len(flow_pairs) >= nb_flow:
                break
            #Find all valid destinations for this source
            candidates = [d for (s, d) in paires_valides if s.id == es_src.id]
            #If the source has at least one valid destination
            if candidates:
                #Randomly pick one
                es_dst = self.rng.choice(candidates)
                #Add the pair
                flow_pairs.append((es_src, es_dst))
 
        #Ensure each distinct destination is used at least once
        #Track already covered destinations
        dst_cov = {d.id for (_, d) in flow_pairs}
        for es_dst in dst_uni:
            #Stop if budget is exhausted
            if len(flow_pairs) >= nb_flow:
                break
            #Skip if this destination is already covered
            if es_dst.id in dst_cov:
                continue
            #Find all valid sources for this destination
            candidates = [s for (s, d) in paires_valides if d.id == es_dst.id]
            #If the destination has at least one valid source
            if candidates:
                #Randomly pick one
                es_src = self.rng.choice(candidates)
                #Add the pair
                flow_pairs.append((es_src, es_dst))
                #Mark this destination as covered
                dst_cov.add(es_dst.id)
 
        #Fill the remaining budget with random selections
        while len(flow_pairs) < nb_flow and paires_valides:
            #Randomly select any valid pair
            es_src, es_dst = self.rng.choice(paires_valides)
            #Add the pair
            flow_pairs.append((es_src, es_dst))

        #Return only the first nb_flow pairs
        return flow_pairs[:nb_flow]



    #Flow Generation
    def generate_flows(self, end_systems):
        """
        Generates nb_flow flows, ensuring that each end system specified by the user is used at least once as a source or destination.
        """
        #Number of flows to generate
        nb_flow = self.Nfl
        #List to store the created flows
        flows = []
 
        # ---- Single-destination topologies ----------------------------
        if self.topology in ("single_node", "line1I/1O", "lineNI/1O", "tree"):
            #All ES except the last one
            src = [es for es in end_systems[:-1]]
            #The last ES is the unique destination
            dst = end_systems[-1]

            paires_valides = [
                (s, dst) for s in src if s.id != dst.id
            ]
            if not paires_valides:
                raise ValueError("No valid source/destination pair.")
            #Generate pairs with maximum coverage
            for i, (es_src, es_dst) in enumerate(self.construct_pairs(nb_flow, paires_valides)):
                # reate Flow objects with unique identifiers
                flows.append(Flow(id=f"V{i+1}", source=es_src.id, destination=es_dst.id))
 
        # ---- lineNI/NO : multiple sources and destinations ---------------
        elif self.topology == "lineNI/NO":
            #Utility function to extract switch index from its ID
            def idx(sw_id):
                return int(sw_id[2:])

            #Separate ES based on their role (source or destination)
            src = [es for es in end_systems if getattr(es, "role", None) == "source"]
            dst = [es for es in end_systems if getattr(es, "role", None) == "destination"]
            #In a linear topology, flows go from left to right so the source must be to the left of the destination
            paires_valides = [
                (s, d) for s in src for d in dst
                if idx(s.sw_id) < idx(d.sw_id)
            ]
            if not paires_valides:
                raise ValueError(
                    "lineNI/NO: no valid source/destination pair (left->right) "
                    "with this number of ESs and switches."
                )
            #Generate pairs with maximum coverage
            for i, (es_src, es_dst) in enumerate(self.construct_pairs(nb_flow, paires_valides)):
                flows.append(Flow(id=f"V{i+1}", source=es_src.id, destination=es_dst.id))
 
        # ---- ring / random :  multiple sources and destinations -----------
        elif self.topology in ("ring", "random"):
            #Separate ES based on their role
            src = [es for es in end_systems if getattr(es, "role", None) == "source"]
            dst = [es for es in end_systems if getattr(es, "role", None) == "destination"]
            if not src or not dst:
                raise ValueError("Insufficient number of end systems.")
            # ------------ ring  ------------------------
            if self.topology == "ring":
                #Function to extract switch index from its ID
                def idx_sw(sw_id):
                    return int(sw_id[2:])
                #Number of switches in the ring
                n = self.Nsw
                #Minimum distance threshold
                dist_max = math.ceil(n/2)
 
                #Calculate circular distance between two switches
                def cyclic_dis(sw_src, sw_dst):
                    return (idx_sw(sw_dst) - idx_sw(sw_src)) % n

                #In a ring, we enforce a minimum distance to ensure sufficiently long paths
                paires_valides = [
                    (s, d) for s in src for d in dst
                    if 1 <= cyclic_dis(s.sw_id, d.sw_id) <= dist_max
                ]
                if not paires_valides:
                    raise ValueError(
                        f"ring: no valid source/destination pair. "
                        f"Increase nb_es or {n}."
                    )
            # ------------ random  ------------------------    
            else:  
                #All pairs are valid as long as source != destination
                paires_valides = [
                    (s, d) for s in src for d in dst if s.id != d.id
                ]
                if not paires_valides:
                    raise ValueError("random: no valid source/destination pair.")
 

            #Generate pairs with maximum coverage
            for i, (es_src, es_dst) in enumerate(self.construct_pairs(nb_flow, paires_valides)):
                flows.append(Flow(id=f"V{i+1}", source=es_src.id, destination=es_dst.id))
 

        #Return the list of generated flows
        return flows
    
    #============================== routing and  the shortest path  =============================================
    def dess_graph(self, switches, end_systems):
        """
        A function that visualizes the network topology as a graph, helping to compute and verify shortest paths.
         resultat:
            SW1:["ES1","ES2","ES10"]
            ES1:["SW1"]
            ES2:["SW1"]
            ES10:["SW1"]
        """
        #Initialize the graph.
        graph: Dict[str, List[str]] = {}

        #Add all switches and end systems as nodes.
        for sw in switches:
            graph.setdefault(sw.id, [])
        for es in end_systems:
            graph.setdefault(es.id, [])

        #Add existing switch-to-switch and switch-to-ES connections.
        for sw in switches:
            for port in sw.output_port:
                graph.setdefault(port.destination, [])
                if port.destination not in graph[sw.id]:
                    graph[sw.id].append(port.destination)

        #Add connections from source end systems to switches.
        for es in end_systems:
            if es.output_port and es.output_port.destination:
                dst = es.output_port.destination
                graph.setdefault(dst, [])
                if dst not in graph[es.id]:
                    graph[es.id].append(dst)

        return graph
    
    def short_path(self,graph: Dict, src: str, dst: str):
        """
        Compute the shortest path between src and dst in an unweighted graph.
            graph:dict of end systeme and switch
            src : Source node ID
            dst : Destination node ID
            la sortie :
                list of Shortest path as a list of node IDs, starting with src and ending with dst.
                If no path exists, returns an empty list.
        """
        if src == dst:
            return [src]
        #BFS to find shortest path in an unweighted graph
        visit = {src}
        file = deque([[src]])
        while file:
            path = file.popleft()
            node = path[-1]
            for neighbor in graph.get(node, []):
                if neighbor == dst:
                    return path + [dst]
                if neighbor not in visit:
                    visit.add(neighbor)
                    file.append(path + [neighbor])
        return None
    
    #compute_routing
    def compute_routing(self, switches, end_systems,flows) -> None:
        """Compute, for each flow, the path (ordered list of switches/ES)
            from its source to its destination."""
        #Build an adjacency-list graph from the network topology
        graph = self.dess_graph(switches, end_systems)
        #Traverse all Flow
        for flow in flows:
            #Find the shortest path between src and dst 
            flow.path = self.short_path(graph, flow.source, flow.destination)


    #Load Calculation
    def load_Calculation(self,switches, flows):
        """
        Constructs, for each output port, the list of flows passing through it (interference structure), based on the routes already calculated in flux.chemin.
        """
        ports_par_switch = {sw.id: sw.output_port for sw in switches}
        interference: Dict[str, List[str]] = {
            p.id: [] for sw in switches for p in sw.output_port
        }
 
        for flow in flows:
            if not flow.path or len(flow.path) < 2:
                continue
            for idx in range(len(flow.path) - 1):
                node, suivant = flow.path[idx], flow.path[idx + 1]
                if node.startswith("SW"):
                    for port in ports_par_switch.get(node, []):
                        if port.destination == suivant:
                            interference[port.id].append(flow.id)
                            break
        return interference

    
    def check_accepted(self, ports_id, interference, rho_min):
        """
        Before performing admission control, verify that each output port can accommodate all the flows traversing it.
        Necessary (but not sufficient) condition:  N_j * rho_min <= R_j
        N_j      = number of flows traversing port j
        rho_min  = (Lmin * 8) / bagmax : minimum possible rate of a flow
        R_j      = bandwidth of port j 
        Returns True if all ports are feasible, and False otherwise.
        """
        accepted = True
        #Get the minimum frame size
        Lmin, _ = self.size
        #Get the maximum BAG value
        bagmax_aff = max(self.bag) if not isinstance(self.bag, tuple) else self.bag[1]

        #Check each output port and the flows traversing it
        for pid, list_flow_ids in interference.items():
            #Number of flows using the current output port
            N_j = len(list_flow_ids)
            #No flow crosses this port, so there is no feasibility constraint
            if N_j == 0:
                continue
            #Get the bandwidth of the current output port
            Rj = ports_id[pid].bandwidth
            #Compute the minimum bandwidth by all flows in this port
            load_min = N_j * rho_min
            #Check if total minimum load must not exceed port capacity
            if load_min > Rj:
                accepted = False
                print(
                    f"[ERROR] Port '{pid}' cannot be used: {N_j} flows cross it,requiring a minimum load of {load_min:.1f} Mbps "
                    f"({N_j} × {rho_min:.4f} Mbps), which exceeds its capacity of {Rj} Mbps.\n"
                    f"  Suggestions:\n"
                    f"    - Increase the output port bandwidth (-R), currently {Rj} Mbps.\n"
                    f"    - Decrease the minimum frame size (-L), currently Lmin={Lmin} bytes. [64,1518]\n"
                    f"    - Increase the maximum bag (-bag), currently bagmax={bagmax_aff} us. [128,16384]\n"
                    f"    - Reduce the number of flows -Nfl .\n"
                    f"    - Run the generation again.",
                    file=sys.stderr
                )
        return accepted
    
    #Admission Control
    def controle_admission(self, switches: List[Switch], flows: List[Flow],interference: Dict[str, List[str]]):
        """
        It processes egress ports in descending order of the number of flows
        passing through them. However, instead of randomly selecting (L, bag) 
        and rejecting the choice if it doesn't fit, the selection range for L is constrained 
        beforehand to guarantee that a valid bag will always exist. 
 
        Principle: rho = L*8/bag is minimized when L is small and bag is large.
        The lowest possible rho is therefore: rho_min = Lmin*8 / bagmax
 
        As long as the available capacity on a port is >= rho_min, a solution (L, bag) is guaranteed to exist.
        One simply needs to select L within the interval [Lmin, L_max], where:
 
            L_max = min(Lmax, floor(capacite_available * bagmax / 8))
 
        and then calculate the smallest valid bag >= L*8/capacite_available (which will automatically be <= bagmax by design). 
        This AVOIDS any capacity-related rejections.
        """
        ports_id = {p.id: p for sw in switches for p in sw.output_port}
        flow_by_id = {f.id: f for f in flows}
        #Minimum and maximum allowed frame sizes
        Lmin, Lmax = self.size

        #Retrieve and sort the possible BAG values
        bag_value = bag_us(self.bag[0],self.bag[-1])
        bagmax = bag_value[-1] 

        #Minimum possible flow rate.
        rho_min = (Lmin * 8) / bagmax  

        #Current aggregate load of each output port
        R_now: Dict[str, float] = {pid: 0.0 for pid in ports_id}
        #List of permitted flows
        flow_accepted_ids: Set[str] = set()
        
        #Sort ports with a large number of flows.
        ports_sorted = sorted(
            interference.keys(),
            key=lambda pid: len(interference[pid]),
            reverse=True,
        )
        #Check the necessary admission condition before starting
        if not self.check_accepted(ports_id, interference, rho_min):
            raise ValueError(
                "Admission control aborted: with the current -L/-BAG/-R parameters, "
                "at least one port cannot accepted all the flows routed through it "
                "(see [ERROR] messages above for details and suggestions)."
            )
       

        #Determine the L and bag parameters to stay within the available capacity.
        def tir_L_bag(capacity_available: float):
            """
            Draw a valid (L_i, bag_i, rho_i) that respects capacity_available,
            bounding L_i in advance to guarantee that a solution exists. 
            Returns (L_i, bag_i, rho_i). Can only fail if capacity_available < rho_min.
            """
            R_available = max(capacity_available, rho_min)
            #Maximum frame size that can be supported with BAGmax
            L_max= min(Lmax, int((R_available * bagmax) / 8))
            #Respect the global maximum frame-size constraint
            L_max = max(L_max, Lmin)  
            #Randomly select the frame size within the valid range
            L_i = self.rng.randint(Lmin, L_max)
            #Minimum BAG required for the selected frame size
            bag_min = (L_i * 8) / R_available

            #Select a valid BAG 
            valid_bags=[]
            for bag in bag_value:
                if bag >= bag_min:
                    valid_bags.append(bag)

            bag_i=self.rng.choice(bag_value)

            #Compute the resulting flow rate
            rho_i = (L_i * 8) / bag_i
            return L_i, bag_i, rho_i

       
        #Browse all Switch ports
        for pid in ports_sorted:
            #Retrieve the list of flows for each port.
            flow_id_list = interference[pid]
            #The number of flows in each port
            N_j = len(flow_id_list)
            #If the port is empty, exit the loop.
            if N_j == 0:
                continue
            #Recover the capacity of each port
            Rj = ports_id[pid].bandwidth
            k = sum(
                1 for flid in flow_id_list
                if flid in flow_accepted_ids 
            )
            #Calculate the reserved flow rate for all existing flows
            rho = max(0, (N_j - k)) * (Lmin * 8) / bagmax
            #Browse the list flows of this Port 
            for flid in list(flow_id_list):
                flow = flow_by_id[flid]
                #Check if the flow is in the list of Allowed flows.
                if flid not in flow_accepted_ids:
                    continue
                #Retrieve the flow rate 
                rho = (flow.size * 8) /flow.bag 
                #Otherwise, add the flow rate to the current port load.
                R_now[pid] += rho 
            
            #Try to accepted the remaining flows traversing this port
            for flid in flow_id_list:
                #Flow already accepted 
                if flid in flow_accepted_ids:
                    continue
                flow = flow_by_id[flid]
                #Calculate remaining port capacity
                capacity_disp = Rj - R_now[pid] - rho
                #Retrieve the choice of L, bag and the rho
                Li, bagi, rhoi = tir_L_bag(capacity_disp)
                #Assign this choice to your flow.
                flow.size, flow.bag = Li, bagi
                #Choose the priority
                flow.priority = (
                    self.rng.randint(0, self.priority_max)
                    if self.policy == "FP/FIFO" else 0
                )
                #Add the flow rate to the current port load.
                R_now[pid] += rhoi
                flow_accepted_ids.add(flid)
                k += 1
        
        #Recover the accepted and rejected Flows
        flow_accepted = [flow_by_id[flid] for flid in flow_accepted_ids]

        #Affects the load on all switch ports
        for pid, load in R_now.items():
            port = ports_id[pid]
            #Load in Mbps
            port.load_mbps = load
            #Load as a percentage of the port capacity.
            port.load_percentage = (
                load / port.bandwidth * 100.0 if port.bandwidth > 0 else 0.0
            )
        #Return the list of accepted flows
        return flow_accepted
   
  


    def generer(self)->configuration:

        #Build switches and their interconnections, then create and attach end systems (Switch ,End System)
        switches,end_systems = self.topology_generation()

        #Create flows ensuring each source and destination is used at least once (only source/destination,unicast)
        flows = self.generate_flows(end_systems)

        #Compute the path (sequence of switches) for each flow through the network
        self.compute_routing(switches, end_systems, flows)

        #Build interference structure to understand resource contention
        interference = self.load_Calculation(switches, flows)

        #Randomly draw traffic parameters (frame size, bag, priority)
        flow_accepted= self.controle_admission(switches, flows, interference)

        #Combine accepted and rejected flows for complete record
        all_flow = flow_accepted

        #Return a configuration object containing all generated elements
        return configuration(type=self.topology, switches=switches, end_systems=end_systems, Flows=all_flow)

    
def save_results(configuration,nom_fichier):
    """
        Saves the complete network configuration to a JSON file.
    """
    #Initialize the results dictionary with metadata
    results={
        "metadata":{
            "nb_Flow":len(configuration.Flows),
            "nb_Switches":len(configuration.switches),
            "nb_End_System":len(configuration.end_systems),
            "topology": configuration.type  
        },
        "end_systems":[],
        "switches":[],
        "Flow":[],
    }
    #save the End System
    for es in configuration.end_systems:
        #Build port dictionary for the end system's output port
        port_dict = {
            "id": es.output_port.id,
            "destination": es.output_port.destination,
            "Bandwidth": es.output_port.bandwidth
        }
        results["end_systems"].append({
            "id":es.id,
            "output_port":port_dict
        })
    #save the Switches
    for sw in configuration.switches:
        #Serialize all output ports with their load information
        output_ports_json = []
        for port in sw.output_port:
            
            port_dict = {
                "id": port.id,
                "destination": port.destination,
                "Bandwidth": port.bandwidth,
                "load_mbps": port.load_mbps,
                "load_percentage":port.load_percentage
            }
            output_ports_json.append(port_dict)
            
        results["switches"].append({
            "id":sw.id,
            "input_port":sw.intput_port,
            "output_port":output_ports_json
            
        })

    #save the Flows
    for fl in configuration.Flows:
            #Flow has a valid path -> mark as accepted
            results["Flow"].append({
                "id":fl.id,
                "source":fl.source,
                "destination":fl.destination,
                "size":fl.size,
                "priority":fl.priority,
                "bag":fl.bag,
                "path":fl.path
            })
    #Write to JSON File
    with open(nom_fichier,"w") as f:
        json.dump(results,f)



def validate_parameters(topology: str,nb_switch: int,nb_es: int,nb_flow: int,size: Optional[tuple] = None,bag: Optional[tuple] = None,bandwidth: Optional[float] = None,
    policy: Optional[str] = None,priority_max: Optional[int] = None):
    """
    Validate the user parameters before starting network generation

    The validation covers two main categories:
        Topology parameters (-T, -Nsw, -Nes, -Nfl)
        Traffic  parameters : (-L, -bag, -R, -Policy, -priority_max)
       generateur avec une erreur claire en amont.

    Returns: error: list of error messages. topology: possibly topology. bag: possibly BAG interval
    """
    #Store all detected validation errors
    error: List[str] = []
   

    ##############################    Topology name     #########################################
    topologies_valides = {
        "single_node", "line1I/1O", "lineNI/1O", "lineNI/NO", "tree", "ring", "random"
    }
    #Check whether the requested topology is supported
    if topology not in topologies_valides:
        error.append(
            f"Topology '{topology}' unknown. Possible values: "
            f"{', '.join(sorted(topologies_valides))}."
        )
        return error
    ##############################    Minimum number of switches     #########################################
    switch_min = {
        "single_node": 1,
        "line1I/1O": 2, "lineNI/1O": 3, "lineNI/NO": 3,
        "tree": 3,
        "ring": 3,
        "random": 3,
    }
    #Retrieve the minimum number of switches of Topology selected
    n_min_sw = switch_min[topology]
    #When the number of switches=1 the topology is Single_node 
    if topology in ("line1I/1O","lineNI/1O","lineNI/NO","tree","ring","random") and nb_switch==1:
            print(f"[WARNING] the number of switches: {nb_switch} is corresponds to single_node \n",
                f"for {topology}: {n_min_sw} switches are indeed required") 
            topology="single_node"
    #When the number of switches=2 the topology is line1I/1O 
    elif topology in ("lineNI/1O","lineNI/NO","tree","random","ring") and nb_switch==2:
            print(f"[WARNING] the number of switches: {nb_switch} is corresponds to line1I/1O  \n"
                  f"for {topology} : {n_min_sw} switches is indeed required")
            topology="line1I/1O"
    else:
        if nb_switch < n_min_sw:
                        error.append(
                            f"Nsw={nb_switch} insufficient for topology '{topology}' (minimum required: {n_min_sw})."
                        )
    ##############################    Number of end systems and flows    #########################################
    #Check the minimum number of end systems and flows for single_node
    if topology == "single_node" and nb_switch >= n_min_sw:
        if nb_es < 2:
            error.append(
                    f"Nes={nb_es} insufficient for 'single_node' with at least 2 end systems required (1 source + 1 destination)."
            )
       #At least one flow is required per source.
        if nb_flow < nb_es - 1:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'single_node' with Nes={nb_es}: at least {nb_es - 1} flows required (1 per source)."
            )
    #Check the minimum number of end systems and flows for line1I/1O
    if topology == "line1I/1O" and nb_switch >= n_min_sw:
        if nb_es < 2:
            error.append(
                    f"Nes={nb_es} insufficient for 'lineNI/1O' with Nsw={nb_switch}: at least {nb_switch + 1} end systems required (1 source per switch + 1 destination)."
            )
        if nb_flow < nb_es - 1:
            error.append(
                   f"Nfl={nb_flow} insufficient for 'line1I/1O' with Nes={nb_es}: at least {nb_es - 1} flows required (1 per source)."
            )
        
    #Check the minimum number of end systems and flows for lineNI/1O
    if topology == "lineNI/1O" and nb_switch >= n_min_sw:
        if nb_es < nb_switch + 1:
            error.append(
                    f"Nes={nb_es} insufficient for 'lineNI/1O' with Nsw={nb_switch}: at least {nb_switch + 1} end systems required (1 source per switch + 1 destination)."
            )
        if nb_flow < nb_es - 1:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'lineNI/1O' with Nes={nb_es}: at least {nb_es - 1} flows required (1 per source)."
            )

   #Check the minimum number of end systems and flows for lineNI/NO
    if topology =="lineNI/NO" and nb_switch >= n_min_sw:
        if nb_es < 2 * nb_switch:
            error.append(
                    f"Nes={nb_es} insufficient for 'lineNI/NO' with Nsw={nb_switch}: at least {2 * nb_switch} end systems required (1 source and 1 destination per switch)."
            )
        if nb_flow < (nb_es + 1) // 2:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'lineNI/NO' with Nes={nb_es}: at least { (nb_es + 1) // 2 } flows required (1 per source)."
            )

    # Check the minimum number of end systems and flows for Tree
    if topology =="tree" and nb_switch >= n_min_sw:
        #Calculate the number of tree levels.
        n = int(math.floor(math.log2(nb_switch + 1)))
        #Calculate the number of switches in complete levels.
        switches_complete = sum(2**k for k in range(n))
        #Switches in the last partial level
        nb_sw_last = nb_switch - switches_complete
        #Unused switches at level n-1
        nb_sw_last_minus_1_unp = 2**(n-1) - int(math.ceil(nb_sw_last / 2))
        #Minimum number of ES: leaves + 1 destination at the root
        nb_es_tree_min = nb_sw_last + nb_sw_last_minus_1_unp + 1

        if nb_es < nb_es_tree_min:
            error.append(
                    f"Nes={nb_es} insufficient for 'tree' with Nsw={nb_switch}: at least {nb_es_tree_min} end "
                    f"systems required ({nb_sw_last + nb_sw_last_minus_1_unp} sources at the leaves + 1 destination at the root)."
            )
        if nb_flow < nb_es - 1:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'tree' with Nes={nb_es}: at least {nb_es - 1} flows required (1 per source)."
            )
        elif nb_flow < nb_es_tree_min - 1:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'tree' with Nes={nb_es}: at least {nb_es_tree_min - 1} flows required (1 per source)."
                )
    #Check the minimum number of end systems and flows for ring
    if topology == "ring" and nb_switch >= n_min_sw:
        if nb_es < 2 * nb_switch  :
                error.append(
                    f"Nes={nb_es} insufficient for 'ring' with Nsw={nb_switch}: at least {2 * nb_switch} end systems required (1 source and 1 destination per switch)."
                )
        if nb_flow < (nb_es + 1) // 2:
            error.append(
                    f"Nfl={nb_flow} insufficient for 'ring' with Nes={nb_es}: at least { (nb_es + 1) // 2 } flows required (1 per source)."
            )
    #Check the minimum number of end systems and flows for random
    if topology == "random" and nb_switch >= n_min_sw:
        if nb_es < nb_switch:
            error.append(
                   f"Nes={nb_es} insufficient for 'random' with Nsw={nb_switch}: at least {nb_switch} end systems required."
            )

        if nb_flow < (nb_es + 1) // 2:
            error.append(
                   f"Nfl={nb_flow} insufficient for 'random' with Nes={nb_es}: at least { (nb_es + 1) // 2 } flows required (1 per source)."
            )

    ##############################   Frame size (-L)    #########################################
    #Validate the minimum and maximum frame sizes.
    if size is not None:
        Lmin, Lmax = size
        if Lmin <= 0 or Lmax <= 0:
            error.append(f"-L={size} invalid: sizes must be > 0.")
        elif Lmin > Lmax:
            error.append(f"-L={size} invalid: Lmin ({Lmin}) > Lmax ({Lmax}).")
        if Lmin < 64 or Lmax > 1518:
            error.append(
                f"L={size} outside the standard Ethernet/AFDX range [64, 1518] bytes."
            )

    ##############################    bag interval (-bag)       #########################################
    #Validate the BAG interval and adjust it to valid power-of-two values.
    if bag is not None:
        Bmin, Bmax = bag
        liste_bag = bag_us(Bmin, Bmax)
        if liste_bag and (liste_bag[0] != Bmin or liste_bag[-1] != Bmax):
            if liste_bag[0]>=128 and liste_bag[-1] <=16384:
                print(
                    f"[WARNING] bag={Bmin}-{Bmax} adjusted to [{liste_bag[0]}, {liste_bag[-1]}]"
                    f"(only powers of 2 are supported)."
                )
                bag=liste_bag
            else:
                print(
                    f"[WARNING] bag={Bmin}-{Bmax} adjusted to [128, 16384] "
                    f"(only powers of 2 are supported)."
                )
                bag=[128,16384]
        if Bmin <= 0 or Bmax <= 0:
            error.append(f"bag={bag} invalid: values must be > 0.")
        elif Bmin > Bmax:
            error.append(f"bag={bag} invalide : Bmin ({Bmin}) > Bmax ({Bmax}).")
        else:
            if not bag_us(Bmin, Bmax):
                error.append(
                    f"bag={bag} contains no power of 2. Correct example: bag 128-16384."
                )

    ##############################    Port bandwidth (-R)     #########################################
    #Validate the port bandwidth.
    if bandwidth is not None:
        if bandwidth <= 0:
            error.append(
                    f"R={bandwidth} invalid: port bandwidth must be > 0 Mbps."
            )
        #Check whether the minimum flow rate can fit within the port bandwidth
        if size is not None and bag is not None and bandwidth > 0:
            Lmin, _ = size
            Bmax = bag[-1]
            if Bmax > 0:
                rho_min = (Lmin * 8) / Bmax
                if rho_min > bandwidth:
                    error.append(
                        f"Inconsistency -L/-bag/-R: the minimum possible data rate "
                        f"for a flow is rho_min = Lmin*8/bagmax = "
                        f"{rho_min:.4f} Mbps, which exceeds -R={bandwidth} "
                        f"Mbps. NO flow can be admitted. Increase -R, "
                        f"decrease Lmin, or increase bagmax."
                    )

    ##############################    Service policy and priority (-priority_max)     #########################################
    #Validate the service policy
    if policy is not None and policy not in ("FIFO", "FP/FIFO"):
        error.append(f"-Policy={policy!r} invalid: possible values 'FIFO' or 'FP/FIFO'.")
    #Validate the maximum priority.
    if priority_max is not None and priority_max < 0:
        error.append(f"priority_max={priority_max} invalid: maximum priority must be >= 0.")
    #Check whether priority_max is relevant for FIFO
    if policy == "FIFO" and priority_max is not None and priority_max > 0:
        error.append(
            f"priority_max={priority_max} has no effect with -Policy=FIFO "
            f"(priority is only used in FP/FIFO)."
        )



    return error,topology,bag



def main():      
    # Command-line argument parser configuration
    parser = argparse.ArgumentParser(
        prog="AFDX_simulator",
        usage="""%(prog)s
                [-h --help]            show this help message       
                [-T --topology]        Network topology type {single_node,line1I/1O,lineNI/1O,lineNI/NO,tree,ring,random}
                [-Nsw --nb_switch]     Number of switches
                [-Nes --nb_end_system] Number of end systems 
                [-Nfl --nb_flow]       Number of flows
                [-L --size]            Packet size interval (bytes)
                [-BAG --bag]           bag interval 
                [-R --bandwidth_port]  Output port Bandwidth
                [-Policy --policy_service] Service policy {FIFO,FP/FIFO}
                [-Pm --priority_max]  highest supported priority
                [-Se --seed]   Random seed
                [-O --output]  Output file
                """,
        epilog="Example: python generator.py --topology lineNI/NO --nb_switch 4 --nb_end_system 6 --nb_flow 20 --size 64-1518 --bag 128-128000 --seed 42"
    )

    #Define the topology parameters
    parser.add_argument(
        "-T", "--topology",
        type=str,
        choices=["single_node", "line1I/1O", "lineNI/1O", "lineNI/NO", "tree", "ring","random"],
        default="single_node",
        help="Type of Network Topology (default: single_node)"
    )
    #Define the NB Switch parameters
    parser.add_argument(
        "-Nsw", "--nb_switch",
        type=int,
        default=None,
        help="Number of Switch (default:1)"
    )

    #Define the NB End System parameters
    parser.add_argument(
        "-Nes", "--nb_end_system",
        type=int,
        default=None,
        help="Number of End System (default: 3 * nb_switch)"
    )

    #Define the NB Flow parameters
    parser.add_argument(
        "-Nfl", "--nb_flow",
        type=int,
        default=None,
        help="Flow interval to generate (default: 3 * nb_switch)"
    )

    #Define the Size parameters
    parser.add_argument(
        "-L", "--size",
        type=str,
        default="64-1518",
        help="Packet size range in bytes (min-max) (default: 64-1518)"
    )
    
    #Define the BAG parameters
    parser.add_argument(
        "-BAG", "--bag",
        type=str,
        default="128-16384",
        help="bag interval in us (min-max) (default: 128-16384)"
    )
    #Define the Bandwidth parameters
    parser.add_argument(
        "-R", "--bandwidth_port",
        type=float,
        default=100.0,
        help="bandwidth of each output port in Mbps (default: 100.0)"
    )
    #Define the policy service parameters
    parser.add_argument(
        "-Policy", "--policy_service",
        type=str,
        choices=["FIFO", "FP/FIFO"],
        default="FIFO",
        help="Switch service policy (default: FIFO)"
    )
    #Define the Priority Max parameters
    parser.add_argument(
        "-Pm", "--priority_max",
        type=int,
        default=None,
        help="The maximum priority used in the FP/FIFO service policy (default: 4)"
    )
    #Define the Seed parameters
    parser.add_argument(
        "-Se","--seed",
        type=int,
        default=None,
        help="Seed for the random number generator (default: clock-based)"
    )
    #Define the Output file parameters
    parser.add_argument(
        "-O", "--output",
        type=str,
        default="Generator_Output.json",
        help="Output file for JSON results (default:Generator_Output.json)"
    )
    groupes_options = [
    ("-T", "--topology"),
    ("-Nsw", "--nb_switch"),
    ("-Nes", "--nb_end_system"),
    ("-Nfl", "--nb_flow"),
    ("-L", "--size"),
    ("-BAG", "--bag"),
    ("-R", "--bandwidth_port"),
    ("-Policy", "--policy_service"),
    ("-Pm", "--priority_max"),
    ("-Se", "--seed"),
    ("-O", "--output"),
    ]

    def check_duplicate_arguments(argv, groupes_options):
        for groupe in groupes_options:
            total = sum(argv.count(opt) for opt in groupe)
            if total > 1:
                print(
                    f"error: the argument {'/'.join(groupe)} was specified more than once.",
                    file=sys.stderr
                )
                sys.exit(2)

    check_duplicate_arguments(sys.argv[1:], groupes_options)    

    #Parse the command-line arguments
    args = parser.parse_args()
    switch_min_defaults = {
        "single_node": 1,
        "line1I/1O": 2, "lineNI/1O": 3, "lineNI/NO": 3,
        "tree": 3, "ring": 3, "random": 3,
    }
    if args.nb_switch is None:
        args.nb_switch = switch_min_defaults.get(args.topology, 1)
    #Force one switch when the single_node topology is selected
    if args.topology == "single_node" and args.nb_switch != 1:
        print(f"[WARNING] single_node: -Nsw={args.nb_switch} ignored -> Nsw=1",
                file=sys.stderr)
        args.nb_switch = 1

    if args.nb_end_system is None:
        args.nb_end_system = 3 * args.nb_switch
    if args.nb_flow is None:
        args.nb_flow = 3 * args.nb_switch
    #Generate a time-based seed when no seed is provided.
    if args.seed is None:
            args.seed = int(time.time() * 1000) % 2**32
    # Résolution de priority_max selon la policy
    if args.priority_max is None:
        args.priority_max = 4 if args.policy_service == "FP/FIFO" else 0
            
    #Convert an interval string into a tuple of integers
    def parse_interval(interval_str):
        parts = interval_str.split("-")
        try:
            valeurs = [int(p) for p in parts]
        except ValueError:
         raise argparse.ArgumentTypeError(
            f"'{interval_str}' invalid: bounds must be integers."
          )
        if len(parts) == 1:
            val = int(parts[0])
            return (val, val)
        return (int(parts[0]), int(parts[1]))
    
    #Parse the packet size and BAG intervals
    try:
        size = parse_interval(args.size)
        bag_range = parse_interval(args.bag)
    except argparse.ArgumentTypeError as e:
        parser.error(str(e))
    
    #Validate the input parameters before generation
    error ,topology,bag= validate_parameters(
        topology=args.topology,
        nb_switch=args.nb_switch,
        nb_es=args.nb_end_system,      
        nb_flow=args.nb_flow,
        size=size,
        bag=bag_range,
        bandwidth=args.bandwidth_port,
        policy=args.policy_service,
        priority_max=args.priority_max,
    )
    #Stop the program if validation errors are found.
    if error:
        parser.error("\n  - " + "\n  - ".join(error))

   
    #Use the validated BAG range
    if bag != bag_range:
        bag_range=bag  

    #Initialize the network generator
    gen=generator(
        seed=args.seed,
        topology=topology,
        nb_switch=args.nb_switch,
        nb_es=args.nb_end_system,
        nb_flow=args.nb_flow,
        size=size,
        bag=bag_range,
        bandwidth_port=args.bandwidth_port,
        policy_service=args.policy_service, 
        priority_max=args.priority_max,
        
    )

    #Run the network generation pipeline
    try:
        config = gen.generer()
    except ValueError as e:
        print(f"\n[ERROR] Generation failed: {e}\n", file=sys.stderr)
        sys.exit(1)

    #Save the generated configuration to a JSON file
    save_results(config, args.output)
    #Display the output file location
    print(f"Generation complete. Results saved in {args.output}")

if __name__ == "__main__":
    main()