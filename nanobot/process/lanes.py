from enum import Enum

class CommandLane(str, Enum):
    """
    Defines the execution lanes for the CommandQueue.
    
    - MAIN: High priority, user-facing interactions. Standard usage.
    - BACKGROUND: Low priority, scheduled tasks (cron), system maintenance.
    - PROBE: For liveness checks or connectivity probes.
    """
    MAIN = "main"
    BACKGROUND = "background"
    PROBE = "probe"
