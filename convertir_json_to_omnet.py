from collections import defaultdict
import json


def lire_json(fichier_json):
    with open(fichier_json, 'r') as f:
        return json.load(f)


# FICHIER .NED

def cree_fichier_ned(config, fichier_sortie="/home/zakarya/omnetpp-workspace/simulation_exemple/simulations/reseauFifo.ned"):

    end_systems = config["end_systems"]
    switches    = config["switches"]
    flux        = config["Flux"]

    #  Positions automatiques 
    x_src  = 80
    x_dst  = 700
    x_sw0  = 250
    dx_sw  = 150
    y_step = 80
    y_base = 80

    contenu_ned = """
import simulation_exemple.AfdxSource;
import simulation_exemple.AfdxSwitch;
import simulation_exemple.AfdxSink;

network AfdxNetwork
{
    @display("bgb=900,600");
    submodules:
"""

    
    src_list = [es for es in end_systems
                if es["port_sortie"]["destination"] is not None]

    dst_list = [es for es in end_systems
                if es["port_sortie"]["destination"] is None]

    for i, es in enumerate(src_list):
        y = y_base + i * y_step
        contenu_ned += f"""
        {es["id"]}: AfdxSource {{
            @display("p={x_src},{y}");
        }}"""

    for i, es in enumerate(dst_list):
        y = y_base + i * y_step
        contenu_ned += f"""
        {es["id"]}: AfdxSink {{
            @display("p={x_dst},{y}");
        }}"""

    # Switches
    for i, sw in enumerate(switches):
        x = x_sw0 + i * dx_sw
        num_in  = len(sw["port_entree"])
        num_out = get_num_out(sw["port_sortie"])
        contenu_ned += f"""
        {sw["id"]}: AfdxSwitch {{
            numIn  = {num_in};
            numOut = {num_out};
            @display("p={x},300");
        }}"""

    #  Connexions 
    contenu_ned += """
    connections:
"""
    for sw in switches:
        for i, es_id in enumerate(sw["port_entree"]):
            if es_id.startswith("ES"):
                contenu_ned += f"""
        {es_id}.out --> {sw["id"]}.in[{i}];"""

    # Switch → ES destination  /  Switch → Switch
    for sw in switches:
        for i, port in enumerate(sw["port_sortie"]):
            dest = port["destination"]
            if dest is None:
                continue

            if dest.startswith("ES"):
                contenu_ned += f"""
        {sw["id"]}.out[{i}] --> {dest}.in;"""

            elif dest.startswith("SW"):
                sw_dest = next((s for s in switches if s["id"] == dest), None)
                if sw_dest is None:
                    continue
                try:
                    idx_in = sw_dest["port_entree"].index(sw["id"])
                    contenu_ned += f"""
        {sw["id"]}.out[{i}] --> {dest}.in[{idx_in}];"""
                except ValueError:
                    contenu_ned += f"""
        {sw["id"]}.out[{i}] --> {dest}.in++;"""

    contenu_ned += "\n}\n"

    with open(fichier_sortie, 'w') as f:
        f.write(contenu_ned)

    print(f"[NED] fichier généré : {fichier_sortie}")
    return fichier_sortie



# FICHIER .INI
def cree_fichier_ini(config, fichier_sortie="/home/zakarya/omnetpp-workspace/simulation_exemple/simulations/omnetpp.ini"):

    switches = config["switches"]
    flux     = config["Flux"]

    contenu_ini = """[General]
network = AfdxNetwork
sim-time-limit = 1s
"""

    #  Sources 
    contenu_ini += "\n# Configuration des sources AFDX\n"

    flux_par_source = defaultdict(list)
    for f in flux:
        flux_par_source[f["source"]].append(f)

    priorites = []

    for source, flux_es in flux_par_source.items():
        num_vls = len(flux_es)
        contenu_ini += f"\n*.{source}.numVLs = {num_vls}\n"

        parts = []
        for f in flux_es:
            bag_s  = f["bag_us"] / 1_000_000.0
            taille = f["taille_bytes"]
            vl_id  = f["id"].replace("V", "")
            prio   = f["priorite"]
            priorites.append(prio)
            parts.append(f"{bag_s}:{taille}:{vl_id}:{prio}")

        vls_config = "|".join(parts)
        contenu_ini += f'*.{source}.vls_config = "{vls_config}"\n'

    #  Switches 
    contenu_ini += "\n# Configuration des switches AFDX\n"

    priorite_max = (max(priorites) + 1) if priorites else 1

    for sw in switches:
        sw_id = sw["id"]
        contenu_ini += f"""
*.{sw_id}.debitLienMbps = 100
*.{sw_id}.numPriorite   = {priorite_max}
"""

        routing_entries = []
        for f in flux:
            chemin   = f["chemin"]
            if chemin is None:
                continue
            vl_id    = f["id"].replace("V", "")
            priorite = f["priorite"]

            if sw_id in chemin:
                idx = chemin.index(sw_id)
                if idx + 1 < len(chemin):
                    next_hop = chemin[idx + 1]
                    out_port = None
                    for k, port in enumerate(sw["port_sortie"]):
                        if port["destination"] == next_hop:
                            out_port = k
                            break
                    if out_port is not None:
                        routing_entries.append(f"VL{vl_id}:{out_port},{priorite}")

        if routing_entries:
            routing_table_str = "; ".join(routing_entries)
            contenu_ini += f'*.{sw_id}.routingTable = "{routing_table_str}"\n'
        else:
            contenu_ini += f'*.{sw_id}.routingTable = ""\n'

    #  Sinks 
    contenu_ini += "\n# Configuration des destinations\n"
    destinations = set(f["destination"] for f in flux)
    sources_set  = set(f["source"]      for f in flux)
    for dest in destinations:
        if dest not in sources_set:
            contenu_ini += f'*.{dest}.displayString = "p=auto"\n'

    with open(fichier_sortie, 'w') as f:
        f.write(contenu_ini)

    print(f"[INI] fichier généré : {fichier_sortie}")
    return fichier_sortie


def get_num_out(port_sortie):
    if isinstance(port_sortie, list):
        return len(port_sortie)
    return 1


def main():
    fichier_json = 'Generator_Output.json'
    config = lire_json(fichier_json)
    cree_fichier_ned(config)
    cree_fichier_ini(config)

if __name__ == "__main__":
    main()