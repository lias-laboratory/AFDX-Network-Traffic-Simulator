#debit est constant 100 mbps
debit_mbps = 100


#class de port de sortie 
class Output_port:
    def __init__(self,id:str,destination:str=None,debit_Mbps:int=0,charge_mbps:float=0.0):
        self.id=id                     #Identifiant de port de sortie
        self.destination=destination   #le prochain noeud(Switch/End System)
        self.debit_Mbps=debit_Mbps     #le debit de cette port
        self.charge_mbps=charge_mbps
        

#class des end System
class End_System:
    def __init__(self, id: str,output_port:Output_port):
        self.id=id #identifiant de ES
        #self.type=type #type de End Sytem(Source,Destination)
        self.output_port = output_port


#class de switch
class Switch:
    def __init__(self,id:str,intput_port:list[str]=None ,output_port:list[Output_port]=None):
        self.id= id  #identifiant de switch
        self.output_port = output_port if output_port is not None else [] #la liste de entre dans le switch
        self.intput_port = intput_port if intput_port is not None else [] #la sortie de switch
      



#class de flux
class Flow:
    def __init__(self,id:str,source:str,destination:list[str],taille_bytes:int=None,priorite:int=None,bag_us:int=None):
        self.id = id #id de Flux F1,F2,F3
        self.source = source #la source de Flux
        self.destination = destination #la destination de Flux
        self.taille_bytes = taille_bytes #la taille de donne 
        self.priorite = priorite #la priorite de flux utilise dans FP/FIFO
        self.bag_us = bag_us #le bag le temps entre transmission


#la topologie de systeme complet
class configuration:
    def __init__(self,end_systems:list[End_System],switches:list[Switch],Flows=list[Flow],type:str=None):
        self.end_systems = end_systems #les ES de reseaux (Source,Destination)
        self.switches = switches #les switch de reseaux
        self.Flows = Flows #les flux de reseaux
        self.types =type #le type de topologie



#calculer le temps de transmission d'un donnee 
def temps_transmission_us(taille_bytes):
    return taille_bytes * 8 / (debit_mbps * 1_000_000) * 1_000_000


#Evenement pour la simulation  
class Event:  
    def __init__(self, time_us: float, type: str,flow_id: str,switch_id:str):
        self.time_us=time_us #le temps arrive cette evenement
        self.type=type     #le type de evenement arrive ou depart ou attente
        self.flow_id=flow_id #le id de FLUX
        self.switch_id=switch_id #le switch qui passe ce event
    #teste le temps le plus petit entre lui et autre temps event
    def __lt__(self, other):
        return self.time_us < other.time_us
   
    

class FlowStats:
    #statistique de flux
    id: int =0
    temps_arrival_us: float = 0.0 #le temps arrive au switch
    temps_depart_us: float = 0.0 #le temps de depart