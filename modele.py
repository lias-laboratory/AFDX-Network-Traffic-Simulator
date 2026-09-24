#Data rate is constant at 100 Mbps
rate = 100


#Output port class
class Output_port:
    def __init__(self,id:str,destination:str=None,bandwidth:int=0,load_mbps:float=0.0):
        self.id=id                     #Output port ID
        self.destination=destination   #The next node (Switch/End System)
        self.bandwidth=bandwidth       #The port throughput
        self.load_mbps=load_mbps       #Charge in Mbps
        

#End System class 
class End_System:
    def __init__(self, id: str,output_port:Output_port):
        self.id=id                     #ES ID
        self.output_port = output_port #Output port of ES


#Switch class
class Switch:
    def __init__(self,id:str,intput_port:list[str]=None ,output_port:list[Output_port]=None):
        self.id= id                    #Switch ID
        self.output_port = output_port if output_port is not None else [] #The list of inputs into the switch
        self.intput_port = intput_port if intput_port is not None else [] #The output of the switch
      



#Flow class 
class Flow:
    def __init__(self,id:str,source:str,destination:list[str],size:int=None,priority:int=0,bag:int=None):
        self.id = id                   #Flow ID
        self.source = source           #The source of the flow
        self.destination = destination #The destination of the flow
        self.size = size               #The size of the data 
        self.priority = priority       #The priority of the flow used in FP/FIFO
        self.bag = bag                 #The time between two transmissions


#la topologie de systeme complet
class configuration:
    def __init__(self,end_systems:list[End_System],switches:list[Switch],Flows=list[Flow],type:str=None):
        self.end_systems = end_systems    #ES of the network (Source, Destination)
        self.switches = switches          #The switches of the network
        self.Flows = Flows                #The flows of the network
        self.type =type                   #The type of topology



#Calculate the transmission time of a data item
def temps_transmission_us(size):
    return size * 8 / (rate * 1_000_000) * 1_000_000


