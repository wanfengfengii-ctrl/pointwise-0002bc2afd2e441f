from dataclasses import dataclass

from capture.events import SampleOrigin


@dataclass(frozen=True, slots=True)
class LatchedSample:
    origin: SampleOrigin
    value: int
