from collections.abc import Iterator
from dataclasses import dataclass

from capture.archive import FixedEvidence
from capture.events import ControlEvent, SampleEvent, SampleOrigin
from qualify.exposure import LatchedSample

# A replay state is the currently open exposure (or None) plus the first
# samples latched so far as (exposure_id, LatchedSample) pairs.
_LatchedMap = frozenset[tuple[str, LatchedSample]]
_State = tuple[str | None, _LatchedMap]


@dataclass(frozen=True, slots=True)
class CompleteInterpretation:
    closed: tuple[tuple[str, LatchedSample | None], ...]
    latch_count: int


def _tick_groups(
    control: tuple[ControlEvent, ...], samples: tuple[SampleEvent, ...]
) -> list[tuple[tuple[ControlEvent, ...], tuple[tuple[int, SampleEvent], ...]]]:
    # Earlier ticks come first; within one tick the cross-channel order is
    # unknown, so each group keeps both channels in their recorded order.
    # Both channels are already non-decreasing in tick, so grouping is linear.
    indexed = tuple(enumerate(samples))
    groups = []
    control_pos = sample_pos = 0
    while control_pos < len(control) or sample_pos < len(indexed):
        pending = []
        if control_pos < len(control):
            pending.append(control[control_pos].tick)
        if sample_pos < len(indexed):
            pending.append(indexed[sample_pos][1].tick)
        tick = min(pending)
        control_run = []
        while control_pos < len(control) and control[control_pos].tick == tick:
            control_run.append(control[control_pos])
            control_pos += 1
        sample_run = []
        while sample_pos < len(indexed) and indexed[sample_pos][1].tick == tick:
            sample_run.append(indexed[sample_pos])
            sample_pos += 1
        groups.append((tuple(control_run), tuple(sample_run)))
    return groups


def _advance_tick(
    states: set[_State],
    control: tuple[ControlEvent, ...],
    samples: tuple[tuple[int, SampleEvent], ...],
    evidence_id: int,
) -> set[_State]:
    # Explore every interleaving of the two channels at this tick. Positions
    # inside each channel stay in recorded order; only the cross-channel
    # interleave varies. Reached states are merged on (state, positions).
    reached: set[_State] = set()
    visited: set[tuple[_State, int, int]] = set()
    stack = [(state, 0, 0) for state in states]
    while stack:
        (open_exposure, latched), control_pos, sample_pos = stack.pop()
        key = (open_exposure, latched, control_pos, sample_pos)
        if key in visited:
            continue
        visited.add(key)
        if control_pos == len(control) and sample_pos == len(samples):
            reached.add((open_exposure, latched))
            continue
        if control_pos < len(control):
            event = control[control_pos]
            opened = event.exposure_id if event.kind == "open" else None
            stack.append(((opened, latched), control_pos + 1, sample_pos))
        if sample_pos < len(samples):
            index, event = samples[sample_pos]
            next_latched = latched
            if open_exposure is not None and all(
                exposure_id != open_exposure for exposure_id, _ in latched
            ):
                origin = SampleOrigin(evidence_id, index, event.event_id)
                next_latched = latched | {(open_exposure, LatchedSample(origin, event.value))}
            stack.append(((open_exposure, next_latched), control_pos, sample_pos + 1))
    return reached


def iter_matching_interpretations(evidence: FixedEvidence) -> Iterator[CompleteInterpretation]:
    control = evidence.channels.control
    samples = evidence.channels.samples
    target = evidence.seal.latch_count
    exposure_ids = tuple(event.exposure_id for event in control if event.kind == "open")
    if target > min(len(samples), len(exposure_ids)):
        return

    states: set[_State] = {(None, frozenset())}
    for control_at_tick, samples_at_tick in _tick_groups(control, samples):
        states = _advance_tick(states, control_at_tick, samples_at_tick, evidence.evidence_id)

    for _, latched in states:
        if len(latched) != target:
            continue
        firsts = dict(latched)
        closed = tuple((exposure_id, firsts.get(exposure_id)) for exposure_id in exposure_ids)
        yield CompleteInterpretation(closed, target)
