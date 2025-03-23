from enum import Enum

class ConnectionType(str, Enum):
    STAIRS = "лестница"  #
    ELEVATOR = "лифт"  #
    SLIDE = "горка"  #
    DOOR = "дверь"  #
    STREET = "улица"  #