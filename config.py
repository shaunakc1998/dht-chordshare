
from collections import OrderedDict
from enum import Enum
from datetime import datetime

IP_ADD = "127.0.0.1"
PORT_NUM = 3006
BUFFER_SIZE = 4096
MAXIMUM_BITS = 16 
TOTAL_NODES = 2 ** MAXIMUM_BITS

class ConsistencyStrategy(Enum):
    EVENTUAL = 1
    SEQUENTIAL = 2
    LINEARIZABLE = 3

class ConcurrencyControl(Enum):
    OPTIMISTIC = 1
    PESSIMISTIC = 2
