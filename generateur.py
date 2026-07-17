import argparse
from collections import deque, defaultdict
import heapq
import json
import random
import time
from typing import Dict, List, Optional
from modele import *

#fonction de cree un bag en puissance de 2
def bag_uss(debut,fin):
    bag=[]
    n=0
    while True:
        puissance = 1 << n
        if puissance > fin:
            break
        if puissance >=debut:
            bag.append(puissance)
        n +=1
    return bag


class generateur:
    """
    seed               : The seed controls the entire randomness of the generator
    nb_flux_range      : number of flows to generate (default: 3 * nb_switch)
    politique_service  : "FIFO" or "FP/FIFO"
    taille_range       : (min, max) Ethernet frame size in bytes, constrained to the range [64, 1518]
    bag_range          : (min, max) BAG in microseconds, sampled from powers of 2
    nom_topologie      : "single_node","line1I/1O","lineNI/1O","lineNI/NO","tree","ring","random"
    nb_switch          : number of Switche
    nb_es              : number of end systems (default: 3 * nb_switch)
    capacite_port_mbps : output port capacity (rate)
    priorite_max       : highest supported priority (0 = highest)
    """

    def __init__(self,seed:int,nb_flux_range=(int,int),politique_service:str=None,
                 taille=(int,int),Bag=(int,int),nb_es: Optional[int] = None,charge_cible=0,nom_topologie:str="simple",
                 nb_switch:int=1,priorite_max: int = 4,max_essais_admission:int = 10,capacite_port_mbps:int=100):
        self.seed=seed                                 #Get the seed
        self.rng=random.Random(seed)                   #Create an RNG from a given seed
        #Get the requested number of flows
        if nb_flux_range is None:
            self.nb_flux_range = 3 * nb_switch
        elif isinstance(nb_flux_range, int):
            self.nb_flux_range = nb_flux_range              
        self.politique_service=politique_service       #Retrieve the used service policy
        self.taille_range=taille                       #Retrieve the used data size
        self.bag_range=Bag                             #Get the used BAG interval
        self.nb_es = nb_es if nb_es is not None else 3 * nb_switch #Get the number of end systems
        self.charge_cible=charge_cible                   #Get the target load threshold
        self.nom_topologie=nom_topologie                 #Get the used topology”
        self.nb_switch=nb_switch                         #Get the used number of switches
        self.priorite_max = priorite_max                 #Get the maximum priority in use
        self.max_essais_admission = max_essais_admission #max number of admission trials
        self.capacite_port_mbps = capacite_port_mbps     #output port capacity (Mbps)
      


    #Topology Generation   
    def generer_topologie(self):
        """
        Builds only the switches and the links between them (no end systems, no flows).
        """
        switches=[]             #list for the switches
        n = self.nb_switch     #number of switches

        # Minimum number of switches required per topology
        minimums = {
            "single_node": 1,
            "line1I/1O": 2, "lineNI/1O": 2, "lineNI/NO": 2,
            "tree": 3, "Tree":3,
            "ring": 4, "Anneau": 4,
            "random": 2,
        }
        #Retrieve the minimum number for each topology
        n_min = minimums.get(self.nom_topologie)
        if n_min is not None and n < n_min:
            raise ValueError(
                f"La topologie '{self.nom_topologie}' necessite au moins "
                f"{n_min} switch(es) (recu : {n})."
            )

        #Single Node Topology
        if self.nom_topologie == "single_node":
            switches.append(Switch(id="SW1"))

        #line1I/1O and lineNI/1O and line Topology    
        elif self.nom_topologie in ("line1I/1O", "lineNI/1O", "lineNI/NO"):   
            #Create all existing switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))
            #link the switches
            for i in range(1, n):
                #Add the outputs for each switch (name, destination, port throughput)
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{i+1}", 
                        destination=f"SW{(i + 1)}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                switches[i].output_port.append(Output_port(
                        id=f"SW{i+1}_OUT_SW{i}",
                        destination=f"SW{i}",
                        debit_Mbps=self.capacite_port_mbps))
               
                #Add the intputs for each switch(name)
                switches[i - 1].intput_port.append(f"SW{i + 1}")
                switches[i].intput_port.append(f"SW{i}")

        #tree topology
        elif self.nom_topologie in ("tree","Tree"):
            #Binary tree of switches converging on a root switch SW1
            #n must be of the form 2^(h+1) - 1; otherwise, it is rounded up to the next odd number 
            h = 0
            while (2 ** (h + 1) - 1) < n:
                h += 1
            n_total = n
            #Create all existing switches 
            for i in range(1, n_total + 1):
                switches.append(Switch(id=f"SW{i}"))
        
            for i in range(2, n_total + 1):
                parent = i // 2
                #Add the outputs for each switch (name, destination, port throughput)
                switches[parent - 1].output_port.append(Output_port(
                        id=f"SW{parent}_OUT_SW{i}", 
                        destination=f"SW{i}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{parent}", 
                        destination=F"SW{parent}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                #Add the intputs for each switch(name)
                switches[parent - 1].intput_port.append(f"SW{i}")
                switches[i - 1].intput_port.append(f"SW{parent}")
            #Leaf switch storage
            self._feuilles_tree = [f"SW{i}" for i in range(n_total // 2 + 1, n_total + 1)]

        #Ring topology
        elif self.nom_topologie in ("ring", "Anneau"):
            #RING: SW1 -> SW2 -> ... -> SWn -> SW1
            #Create all existing switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))
            for i in range(1, n + 1):
                suivant = (i % n) + 1
                #Add the outputs for each switch (name, destination, port throughput)
                switches[i - 1].output_port.append(Output_port(
                        id=f"SW{i}_OUT_SW{suivant}", 
                        destination=f"SW{suivant}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                #Add the intputs for each switch(name)
                switches[suivant - 1].intput_port.append(f"SW{i}")

        #Random topology
        elif self.nom_topologie == "random":
            """Random spanning tree via a Prüfer sequence, followed by the addition of extra edges to introduce cycles."""
            #Create all existing switches
            for i in range(1, n + 1):
                switches.append(Switch(id=f"SW{i}"))
            #Retrieve the edges created by Prüfer.
            aretes = self.arbre_couvrant_prufer(n)
            #Total number of links [between n-1 and n(n-1)/2]
            liens_min = n - 1 
            liens_max = n * (n - 1) // 2
            #randomly generates the number of links created
            nb_liens_total = self.rng.randint(liens_min, liens_max)
            #Number of links to add to the spanning tree created by Prüfer's method
            k = nb_liens_total - liens_min 
            aretes |= self.aretes_supplementaires(n, aretes, k)
            for (a, b) in aretes:
                #Add the outputs for each switch (name, destination, port throughput)
                switches[a - 1].output_port.append(Output_port(
                        id=f"SW{a}_OUT_SW{b}", 
                        destination=f"SW{b}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                switches[b - 1].output_port.append(Output_port(
                        id=f"SW{b}_OUT_SW{a}", 
                        destination=f"SW{a}", 
                        debit_Mbps=self.capacite_port_mbps
                        ))
                #Add the intputs for each switch(name)
                switches[a - 1].intput_port.append(f"SW{b}")
                switches[b - 1].intput_port.append(f"SW{a}")

        else:
            raise ValueError(f"Unknown topology : {self.nom_topologie}")
    
        return switches
    #Generate spanning tree
    def arbre_couvrant_prufer(self, n: int) -> set:
        """Constructs a uniform random spanning tree on n switches using a Prüfer sequence"""
        #if we have a single switch
        if n <= 1:
            #no inter-switch links
            return set()
        #if we just have two switches
        if n == 2:
            return {(1, 2)}
        
        #Generate a random Prüfer sequence of length n-2. 
        sequence = [self.rng.randint(1, n) for _ in range(n - 2)]
        #Decoding the Prüfer sequence into edges
        degre = [1] * (n + 1)
        for s in sequence:
            degre[s] += 1
        aretes = set()
        feuilles = [i for i in range(1, n + 1) if degre[i] == 1]
        heapq.heapify(feuilles)
        for s in sequence:
            feuille = heapq.heappop(feuilles)
            a, b = tuple(sorted((feuille, s)))
            aretes.add((a, b))
            degre[feuille] -= 1
            degre[s] -= 1
            if degre[s] == 1:
                heapq.heappush(feuilles, s)
        #Add the final edge (the 2 remaining nodes of degree 1)
        derniers = [i for i in range(1, n + 1) if degre[i] == 1]
        a, b = tuple(sorted(derniers[:2]))
        aretes.add((a, b))
        return aretes
    

    
    def aretes_supplementaires(self, n: int, aretes_exist: set, k: int) -> set:
        """Select exactly k additional edges from among all pairs of switches not already connected by the spanning tree."""
        all_paires_rest = [
            (a, b)
            for a in range(1, n + 1)
            for b in range(a + 1, n + 1)
            if (a, b) not in aretes_exist
        ]
        k = min(k, len(all_paires_rest))
        return set(self.rng.sample(all_paires_rest, k))
    
    #End System Generation
    def generer_end_systems(self,switches):
        """
        Create the list ES_1, ..., ES_{N_es} associated with the switches according to the rule imposed by the chosen topology.
        """
        end_systems=[]   #list for storing end systems
        #Topologies with multiple sources and a single destination 
        if self.nom_topologie in("single_node","line1I/1O","lineNI/1O"):
            #Retrieve all switches except the last one.       
            if self.nom_topologie == "lineNI/1O":
                switches_source = [switch.id for switch in switches]
            elif len(switches) > 1:
                switches_source = [switches[0].id]   # line1I/1O : uniquement SW1
            else:
                switches_source = [switches[0].id]   # single_node
            n_dest = 1
            n_src = max(1, self.nb_es - n_dest)
            #Create the source end systems and connect them to the switch
            switches_par_id = {sw.id: sw for sw in switches}
            for i in range(1, n_src + 1):
                idx = (i - 1) % len(switches_source)
                sw_id = switches_source[idx]
                end_systems.append(End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,           
                                debit_Mbps=self.capacite_port_mbps            
                            )))
                #Add ES{i} as an input port of the switch
                switches_par_id[sw_id].intput_port.append(f"ES{i}")
            #Create the destination end systems and connect them to their switch
            sw_dest_id = switches[-1].id
            end_systems.append(End_System(
                    id=f"ES{n_src + 1}",
                    output_port=Output_port(
                                id=f"ES{n_src + 1}_IN",
                                debit_Mbps=self.capacite_port_mbps
                            )))
            #Add the switch egress port -> destination ES
            for sw in switches:
                if sw.id == sw_dest_id:
                    sw.output_port.append(Output_port(
                            id=f"{sw_dest_id}_OUT_ES{n_src + 1}",
                            destination=f"ES{n_src + 1}",
                            debit_Mbps=self.capacite_port_mbps
                        ))
                    break
        #tree Topology
        elif self.nom_topologie =="tree":
            feuilles = getattr(self, "_feuilles_tree", None) or [switches[-1].id]
            nb_feuilles = len(feuilles)
            n_dest = 1
            n_src = max(1, self.nb_es - n_dest)
            switches_par_id = {sw.id: sw for sw in switches}
            #Create the source end systems and connect them to the switch.
            for i in range(1, n_src + 1):
                idx = (i - 1) % nb_feuilles
                sw_id = feuilles[idx]
                end_systems.append(End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,           
                                debit_Mbps=self.capacite_port_mbps            
                            )))
                #Add ES{i} as an input port of the switch
                switches_par_id[sw_id].intput_port.append(f"ES{i}")
            #Create the destination end systems and connect them to their switch
            sw_dest_id = switches[0].id
            end_systems.append(End_System(
                    id=f"ES{n_src + 1}",
                    output_port=Output_port(
                                id=f"ES{n_src + 1}_IN",
                                debit_Mbps=self.capacite_port_mbps
                            )))
            #Add the switch egress port -> destination ES
            switches_par_id[sw_dest_id].output_port.append(Output_port(
                    id=f"{sw_dest_id}_OUT_ES{n_src + 1}",
                    destination=f"ES{n_src + 1}",
                    debit_Mbps=self.capacite_port_mbps
            ))
        #lineNI/NO Topology
        elif self.nom_topologie =="lineNI/NO":
            switches_par_id = {sw.id: sw for sw in switches}
            switches_ids = [sw.id for sw in switches]
            nb_sw=len(switches)
            #deux compteur pour End system source et destination
            compteur_source = 0
            compteur_dest = 0
            for i in range(1, self.nb_es + 1):
                role = "source" if i % 2 == 1 else "destination"
                #si le role est source on fait ça
                if role == "source":
                    sw_id = switches_ids[compteur_source % nb_sw]
                    compteur_source += 1
                    es = End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                            id=f"ES{i}_OUT_{sw_id}",
                            destination=sw_id,
                            debit_Mbps=self.capacite_port_mbps
                        ))
                    switches_par_id[sw_id].intput_port.append(f"ES{i}")
                #si le role est destination on fait ça
                else:  
                    sw_id = switches_ids[compteur_dest % nb_sw]
                    compteur_dest += 1
                    es = End_System(
                        id=f"ES{i}",
                        output_port=Output_port(
                            id=f"ES{i}_IN",
                            debit_Mbps=self.capacite_port_mbps
                        ))
                    switches_par_id[sw_id].output_port.append(Output_port(
                        id=f"{sw_id}_OUT_ES{i}",
                        destination=f"ES{i}",
                        debit_Mbps=self.capacite_port_mbps
                     ))
                  
                es.role = role
                es.sw_id = sw_id   
                end_systems.append(es)

        #les topologies avec plusieurs source et plusieurs destination
        elif self.nom_topologie in("ring","random"): 
            #Repartis en round-robin sur les switches eligibles
            switches_par_id = {sw.id: sw for sw in switches}
            switches_ids = [sw.id for sw in switches]
            nb_sw = len(switches)
            compteur_source = 0
            compteur_dest = 0
            for i in range(1, self.nb_es + 1):
                role = "source" if i % 2 == 1 else "destination"
                if role =="source":
                    sw_id = switches_ids[compteur_source % nb_sw]
                    compteur_source += 1
                    es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_OUT_{sw_id}",
                                destination=sw_id,
                                debit_Mbps=self.capacite_port_mbps    
                            ))
                    #Ajouter ES{i} comme port d'entree du switch
                    switches_par_id[sw_id].intput_port.append(f"ES{i}") 
                elif role=="destination":
                    sw_id = switches_ids[compteur_dest % nb_sw]
                    compteur_dest += 1
                    es = End_System(
                            id=f"ES{i}",
                            output_port=Output_port(
                                id=f"ES{i}_IN",
                                debit_Mbps=self.capacite_port_mbps    
                            ))
                    #Ajouter le port de sortie reciproque switch -> ES
                    switches_par_id[sw_id].output_port.append(Output_port(
                        id=f"{sw_id}_OUT_ES{i}",
                        destination=f"ES{i}",
                        debit_Mbps=self.capacite_port_mbps
                    ))
                es.role = role
                es.sw_id = sw_id
                end_systems.append(es)
                
                
                          
        return end_systems
    

    #Flow Generation
    def generer_flux(self, end_systems):
    
        nb_flux = self.nb_flux_range

        #initialize an empty list to store the generated flows
        flows=[]  
        #Topology with single destination(single_node,line1I/1O,lineNI/1O,tree)  
        if self.nom_topologie in("single_node","line1I/1O","lineNI/1O","tree"):
            #Get the existing end systems (source and destination)
            sources = [es for es in end_systems[:-1]]
            destination = end_systems[-1]
            for i in range(nb_flux):
                es_src = self.rng.choice(sources)
                # Contrainte unicast : la source ne peut pas etre la meme ES que la destination
                if es_src.id == destination.id and len(sources) > 1:
                    while es_src.id == destination.id:
                        es_src = self.rng.choice(sources)
                #Create the flows
                flows.append(Flow(
                                id=f"V{i+1}", 
                                source=es_src.id, 
                                destination=destination.id
                            ))
        #line Topology         
        elif self.nom_topologie in("lineNI/NO"):
           #Garantir le chemin strictement gauche --> droit, roles fixes
            def idx(sw_id):
                return int(sw_id[2:])
            #Get the existing end systems (source and destination)
            sources = [es for es in end_systems if getattr(es, "role", None) == "source"]
            destinations = [es for es in end_systems if getattr(es, "role", None) == "destination"]
            #Valid pairs: the source index is strictly smaller than the destination index
            paires_valides = [
                (s, d) for s in sources for d in destinations
                if idx(s.sw_id) < idx(d.sw_id)
            ]
            if not paires_valides:
                raise ValueError(
                   "lineNI/NO: no valid source/destination pair (left->right) "
                    "with this number of ES and switches."
                )
            #Create the flows
            for i in range(nb_flux):
                #Select a random source/destination pair from the generated pairs
                es_src, es_dst = self.rng.choice(paires_valides)
                flows.append(Flow(
                                id=f"V{i+1}", 
                                source=es_src.id, 
                                destination=es_dst.id
                            ))
        #Random and Ring Topology 
        elif self.nom_topologie in("ring","random"):
            #Retrieve the existing end systems (source, destination)
            sources = [es for es in end_systems if getattr(es, "role", None) == "source"]
            destinations = [es for es in end_systems if getattr(es, "role", None) == "destination"]

            if not sources or not destinations:
                raise ValueError("The number of end systems is too low")
            #Ring topology
            if self.nom_topologie =="ring":
                def idx_sw(sw_id):
                    return int(sw_id[2:])
                #Return the number of switches
                n = self.nb_switch
                #At least half of the switches must be traversed by each flow.
                seuil_min = n / 2
                #Return the number of switches traversed from sw_src to sw_dst on the ring.
                def distance_circulaire(sw_src, sw_dst):
                    return (idx_sw(sw_dst) - idx_sw(sw_src)) % n 
                #Retrieve all valid (source, destination) end system pairs
                paires_valides = [
                    (s, d) for s in sources for d in destinations
                    if s.sw_id != d.sw_id and distance_circulaire(s.sw_id, d.sw_id) >= seuil_min
                ]
               
                if not paires_valides:
                    raise ValueError(
                     f"ring: no valid source/destination end system pair exists. "
                       f"Increase nb_es or {n}."
                    )
                #Create Flow objects for each selected valid (source, destination) pair.
                for i in range(nb_flux):
                    es_src, es_dst = self.rng.choice(paires_valides)
                    flows.append(Flow(
                            id=f"V{i+1}",
                            source=es_src.id,
                            destination=es_dst.id
                        ))
            #Random topology
            else :
                for i in range(nb_flux):
                    #Randomly select source and destination end systems 
                    es_src = self.rng.choice(sources)
                    es_dst = self.rng.choice(destinations) 
                    #Skip if source and destination are the same
                    if es_src.id == es_dst.id:
                        continue
                    #Create Flow objects for each selected valid
                    flows.append(Flow(
                                id=f"V{i+1}",
                                source=es_src.id, 
                                destination=es_dst.id
                            ))

        return flows
    
    #============================== routing and  the shortest path  =============================================
    def dess_graph(self,switches, end_systems, oriente: bool=False):
        """ 
        A function that visualizes the network topology as a graph, helping to compute and verify shortest paths. 
        resultat:
            SW1:["ES1","ES2","ES10"]
            ES1:["SW1"]
            ES2:["SW1"]
            ES10:["SW1"]
        """
        graphe: Dict[str, List[str]] = {}

        def add_edge(a, b, bidirectionnel):
            #Add an edge between switch a and switch b
            graphe.setdefault(a, [])
            graphe.setdefault(b, [])
            if b not in graphe[a]:
                graphe[a].append(b) # a -> b
            if bidirectionnel and a not in graphe[b]:
                graphe[b].append(a)  # b -> a (non oriente)
        #Traverse all switches
        for sw in switches:
            #Iterate over all output ports of the given switch
            for port in sw.output_port:
                dest_est_switch = port.destination.startswith("SW")
                #Add the destination node to the graph with its switch ID
                add_edge(sw.id, port.destination, bidirectionnel=not (oriente and dest_est_switch))
        #Traverse all End System
        for es in end_systems:
            graphe.setdefault(es.id, [])
            #Iterate over all output ports of the given End System
            if es.output_port and es.output_port.destination:
                #Add the destination node to the graph with its End System ID
                add_edge(es.id, es.output_port.destination, bidirectionnel=True)
        return graphe

    
    def courte_chemin(self,graphe: Dict, src: str, dst: str):
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
        visites = {src}
        file = deque([[src]])
        while file:
            chemin = file.popleft()
            noeud = chemin[-1]
            for voisin in graphe.get(noeud, []):
                if voisin == dst:
                    return chemin + [dst]
                if voisin not in visites:
                    visites.add(voisin)
                    file.append(chemin + [voisin])
        return None
    
    #Routage
    def routage(self, switches, end_systems,flows) -> None:
        """Compute, for each flow, the path (ordered list of switches/ES)
            from its source to its destination."""
        oriente = self.nom_topologie in ("ring", "Anneau")
        #Build an adjacency-list graph from the network topology
        graphe = self.dess_graph(switches, end_systems, oriente=oriente)
        #Traverse all Flow
        for flux in flows:
            #Find the shortest path between src and dst 
            flux.chemin = self.courte_chemin(graphe, flux.source, flux.destination)


    #Load Calculation
    def load_Calculation(self,switches, flows):
        """
            For each output port, return the list of flow IDs that traverse it.
            This depends only on the routing (computed paths). 
            return:
                port_id: [flow_id1, flow_id2, ...]
        """
        interference: Dict[str, List[str]] = {}
        #Map switch_id -> list of output ports
        ports_par_switch = {sw.id: sw.output_port for sw in switches}

        for flux in flows:
            #Skip flows without a valid path
            if not flux.chemin or len(flux.chemin) < 2:
                continue
            #Walk through the path and identify every link (noeud -> suivant)
            for idx in range(len(flux.chemin) - 1):
                noeud, suivant = flux.chemin[idx], flux.chemin[idx + 1]
                #Only consider links leaving a switch
                if noeud.startswith("SW"):
                    for port in ports_par_switch.get(noeud, []):
                        if port.destination == suivant:
                            #Associate this flow to this port
                            interference.setdefault(port.id, []).append(flux.id)
                            break
        return interference
    

    #Admission Control
    def controle_admission(self, switches: List[Switch], flows: List[Flow],interference: Dict[str, List[str]]):
        """
        For each flow, sample:
          - the frame size L_i in [64,1518] bytes
          - the BAG_i, a power of 2 in bag_range
          - the priority p_i in [0, PriMax] if the policy is FP/FIFO
        Then compute rho_i = L_i * 8 / BAG_i (Mbps) eand verify that the cumulative load of each port along 
        the path does not exceed its capacity. If it exceeds it, the parameters are discarded (up to max_essais_admission times).
        """
        #Build mapping: port_id -> Output_port
        ports_par_id: Dict[str, Output_port] = {p.id: p for sw in switches for p in sw.output_port}
        #Build mapping: switch_id -> list of output ports
        ports_par_switch = {sw.id: sw.output_port for sw in switches}
        #Cumulative load on each port (in Mbps)
        charge_cumulee: Dict[str, float] = {pid: 0.0 for pid in ports_par_id}
        #Possible BAG values (in µs)
        valeurs_bag_possibles = bag_uss(*self.bag_range)

        flux_admis: List[Flow] = []
        flux_rejetes: List[Flow] = []

        for flux in flows:
            #Skip flows without a valid path
            if not flux.chemin or len(flux.chemin) < 2:
                flux.rejete = True
                flux_rejetes.append(flux)
                continue

            #Identify all ports traversed by this flow (for admission check)
            ports_du_chemin = []
            for idx in range(len(flux.chemin) - 1):
                noeud, suivant = flux.chemin[idx], flux.chemin[idx + 1]
                if noeud.startswith("SW"):
                    for port in ports_par_switch.get(noeud, []):
                        if port.destination == suivant:
                            ports_du_chemin.append(port.id)
                            break

            admis = False
            for _ in range(self.max_essais_admission):
                #Randomly generate flow parameters
                L = self.rng.randint(*self.taille_range)
                BAG = self.rng.choice(valeurs_bag_possibles)
                priorite = self.rng.randint(0, self.priorite_max) if self.politique_service == "FP/FIFO" else 0
                #Flow rate Di in Mbps: D_i = L_i * 8 / BAG_i
                D = (L * 8) / BAG 

                #Check that adding this flow does not exceed capacity on ANY port of its path
                if all(charge_cumulee[pid] + D <= self.capacite_port_mbps for pid in ports_du_chemin):
                    #Accept the flow: update cumulative loads
                    for pid in ports_du_chemin:
                        charge_cumulee[pid] += D
                    #Save taille and BAG and Priorite in the Flow
                    flux.taille_bytes, flux.bag_us, flux.priorite = L, BAG, priorite
                    admis = True
                    break

            if admis:
                flux.rejete = False
                flux_admis.append(flux)
            else:
                flux.rejete = True
                flux.chemin = "REJETE"
                flux_rejetes.append(flux)

        #Report final loads on Output_port objects for JSON export
        for pid, charge in charge_cumulee.items():
            port = ports_par_id[pid]
            port.charge_mbps = charge
            port.charge_porcentage = (charge / port.debit_Mbps * 100.0) if port.debit_Mbps > 0 else 0.0

        return flux_admis, flux_rejetes
    #==========================Removal of unused end systems==========================================
    #End System Pruning
    def elaguer_end_systems(self,end_systems,swithces,flux_admis):
        """ Delete all end systems that are neither source nor destination of any admitted flow."""
        es_utilises = set()
        for flux in flux_admis:
            es_utilises.add(flux.source)
            es_utilises.add(flux.destination)
        #Cleanup of switch ports 
        for sw in swithces:
            sw.intput_port =[
                pid for pid in sw.intput_port
                if not pid.startswith("ES") or pid in es_utilises
            ]  
            sw.output_port = [
            port for port in sw.output_port
            if not port.destination.startswith("ES") or port.destination in es_utilises
            ] 
        return [es for es in end_systems if es.id in es_utilises]
    


    def generer(self)->configuration:
        #Topology Generation
        switches = self.generer_topologie()
        #End System Generation
        end_systems = self.generer_end_systems(switches)
        #Flow Generation (only source/destination , unicast)
        flows = self.generer_flux(end_systems)
        #Routing
        self.routage(switches, end_systems, flows)
        #Load Calculation (structure d'interference, avant les parametres de trafic)
        interference = self.load_Calculation(switches, flows)
        #Admission Control (tirage des parametres + verification d'admissibilite)
        flux_admis, flux_rejetes = self.controle_admission(switches, flows, interference)
        #End System Pruning
        end_systems = self.elaguer_end_systems(end_systems,switches,flux_admis)

        toutes_les_flux = flux_admis + flux_rejetes
        return configuration(type=self.nom_topologie, switches=switches, end_systems=end_systems, Flows=toutes_les_flux)
    
def sauvegarder_resultat(configuration,nom_fichier):
    results={
        "metadata":{
            "nb_Flux":len(configuration.Flows),
            "nb_Switches":len(configuration.switches),
            "nb_End_System":len(configuration.end_systems),
            "nom_topologie": configuration.types  
        },
        "end_systems":[],
        "switches":[],
        "Flux":[],
        "Flux_refuser":[]
    }
    #save the End System
    for es in configuration.end_systems:
      
        port_dict = {
            "id": es.output_port.id,
            "destination": es.output_port.destination,
            "debit_Mbps": es.output_port.debit_Mbps
        }
        results["end_systems"].append({
            "id":es.id,
            #"type":es.type
            "port_sortie":port_dict
        })
    #save the Switches
    for sw in configuration.switches:
        
        output_ports_json = []
        for port in sw.output_port:
            
            port_dict = {
                "id": port.id,
                "destination": port.destination,
                "debit_Mbps": port.debit_Mbps,
                "charge_Mbps": port.charge_mbps,
                "charge_porsentage":port.charge_porcentage
            }
            output_ports_json.append(port_dict)
            
        results["switches"].append({
            "id":sw.id,
            "port_entree":sw.intput_port,
            "port_sortie":output_ports_json
            
        })

    #save the Flux
    flux_refuse=[]
    for fl in configuration.Flows:
        if fl.chemin is None or fl.chemin == "REJETE":
            flux_refuse.append(fl.id)
            results["Flux_refuser"].append({
                "id":fl.id,
                "source":fl.source,
                "destination":fl.destination,
                "taille_bytes":fl.taille_bytes,
                "priorite":fl.priorite,
                "bag_us":fl.bag_us,
                "chemin":fl.chemin
            })
            
        else:
            results["Flux"].append({
                "id":fl.id,
                "source":fl.source,
                "destination":fl.destination,
                "taille_bytes":fl.taille_bytes,
                "priorite":fl.priorite,
                "bag_us":fl.bag_us,
                "chemin":fl.chemin
            })
    with open(nom_fichier,"w") as f:
        json.dump(results,f)
def main():      
    # Command-line argument parser configuration
    parser = argparse.ArgumentParser(
        prog="AFDX_simulator",
        epilog="Example: python generateur.py --topology lineNI/NO --nb_switch 4 --nb_end_system 6 --nb_flux 20 --size 64-1518 --bag 128-128000 --seed 42"
    )

    # Arguments of topology
    parser.add_argument(
        "-T", "--topology",
        type=str,
        choices=["single_node", "line1I/1O", "lineNI/1O", "lineNI/NO", "tree", "ring","random"],
        default="single_node",
        help="Type of Network Topology (default: single_node)"
    )
    parser.add_argument(
        "-Nsw", "--nb_switch",
        type=int,
        default=1,
        help="Number of Switch (default: 1)"
    )

    parser.add_argument(
        "-Nes", "--nb_end_system",
        type=int,
        default=None,
        help="Number of End System (default: 3)"
    )


    parser.add_argument(
        "-Nfl", "--nb_flux",
        type=int,
        default=None,
        help="Flow interval to generate (default: 3)"
    )

    parser.add_argument(
        "-L", "--size",
        type=str,
        default="64-1518",
        help="Packet size range in bytes (min-max) (default: 64-1518)"
    )
    

    parser.add_argument(
        "-BAG", "--bag",
        type=str,
        default="128-16384",
        help="BAG interval in us (min-max) (default: 128-16384)"
    )
    parser.add_argument(
        "-C", "--capacity_port",
        type=float,
        default=100.0,
        help="Capacity of each output port in Mbps (default: 100.0)"
    )

    # Arguments pour la politique et le contrôle
    parser.add_argument(
        "-Policy", "--policy_service",
        type=str,
        choices=["FIFO", "FP/FIFO"],
        default="FIFO",
        help="Switch service policy (default: FIFO)"
    )

    
    # Autres arguments
    parser.add_argument(
        "-Se","--seed",
        type=int,
        default=None,
        help="Seed for the random number generator (default: clock-based)"
    )

    parser.add_argument(
        "-O", "--output",
        type=str,
        default="Generator_Output.json",
        help="Output file for JSON results (default:Generator_Output.json)"
    )

    # Analyse des arguments
    args = parser.parse_args()

    #Handling of intervals (e.g., "10-50" → (10, 50))
    def parse_interval(interval_str):
        """Parse an interval string such as '10-50' or '10'"""
        if interval_str is None:
            return None  # Retourne None si la chaîne est None
        parts = interval_str.split("-")
        if len(parts) == 1:
            val = int(parts[0])
            return (val, val)  # Valeur unique
        return (int(parts[0]), int(parts[1]))


    #Get the interval for the frame size
    taille_range = parse_interval(args.size)
    #get the interval for the BAG values
    bag_range = parse_interval(args.bag)

    #Generate a seed if none is provided
    if args.seed is None:
        args.seed = int(time.time() * 1000) % 2**32

   
    gen=generateur(
        seed=args.seed,
        nom_topologie=args.topology,
        nb_switch=args.nb_switch,
        nb_es=args.nb_end_system,
        nb_flux_range=args.nb_flux,
        taille=taille_range,
        Bag=bag_range,
        capacite_port_mbps=args.capacity_port,
        politique_service=args.policy_service, 
        
       
        
    )
    config = gen.generer()
    sauvegarder_resultat(config, args.output)
    print(f"Simulation terminee. Resultats sauvegardes dans {args.output}")
    print(f"Flux admis : {sum(1 for f in config.Flows if not f.rejete)} / {len(config.Flows)}")


if __name__ == "__main__":
    main()       