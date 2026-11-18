from collections.abc import Iterator
from dataclasses import dataclass

from capture.archive import FixedEvidence
from qualify.exposure import LatchedSample, first_in_window


@dataclass(frozen=True, slots=True)
class CompleteInterpretation:
    closed: tuple[tuple[str, LatchedSample | None], ...]
    latch_count: int


def iter_matching_interpretations(evidence: FixedEvidence) -> Iterator[CompleteInterpretation]:
    control = evidence.channels.control
    samples = evidence.channels.samples
    target = evidence.seal.latch_count
    if target > min(len(samples), len(evidence.batch.manifest.exposure_ids)):
        return

    closed = []
    cursor = 0
    for opening, closing in zip(control[::2], control[1::2]):
        cursor, first = first_in_window(evidence.evidence_id, samples, cursor, opening.tick, closing.tick)
        closed.append((opening.exposure_id, first))

    count = sum(first is not None for _, first in closed)
    yield CompleteInterpretation(tuple(closed), count)
