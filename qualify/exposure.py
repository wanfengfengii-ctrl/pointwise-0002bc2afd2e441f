from dataclasses import dataclass

from capture.events import SampleEvent, SampleOrigin


@dataclass(frozen=True, slots=True)
class LatchedSample:
    origin: SampleOrigin
    value: int


def first_in_window(
    evidence_id: int,
    samples: tuple[SampleEvent, ...],
    start_index: int,
    opening_tick: int,
    closing_tick: int,
) -> tuple[int, LatchedSample | None]:
    index = start_index
    while index < len(samples) and samples[index].tick < opening_tick:
        index += 1
    if index == len(samples) or samples[index].tick >= closing_tick:
        return index, None

    event = samples[index]
    first = LatchedSample(SampleOrigin(evidence_id, index, event.event_id), event.value)
    while index < len(samples) and samples[index].tick < closing_tick:
        index += 1
    return index, first
