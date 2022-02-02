import enum

class State(str, enum.Enum):
    NotStarted = "NotStarted"
    TakingBets = "TakingBets"
    Running = "Running"
    Over = "Over"

class Packets(int, enum.Enum):
    PING = 50
    VERSION = 1
    GAME_STATE = 3
    TICK = 4
    BET = 5

