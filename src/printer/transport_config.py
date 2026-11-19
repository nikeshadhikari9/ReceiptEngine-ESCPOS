
from dataclasses import dataclass
from typing import Optional, Literal


@dataclass
class TransportConfig:
    transport_type: Literal["USB", "serial", "network"]

    device: Optional[str] = None
    host: Optional[str] = None
    port: Optional[int] = None
    timeout: int = 5
