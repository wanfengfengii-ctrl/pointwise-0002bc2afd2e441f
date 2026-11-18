from tests import ArchiveTestCase, SOURCE, qualification_signature


def boundary_recording(control, samples, latch_count):
    return {
        "source_id": SOURCE,
        "control": control,
        "samples": samples,
        "seal": {"kind": "seal", "latch_count": latch_count},
    }


class SameTickInterleavingTests(ArchiveTestCase):
    """Regression: same-tick cross-channel order is unknown, so qualification
    must replay every complete order and keep only the ones whose latch count
    matches the device seal."""

    def test_open_tick_reading_may_precede_or_follow_open(self):
        batch = self.station.registry.register("coil-open", SOURCE, ("A",))
        document = boundary_recording(
            [{"tick": 1, "kind": "open", "exposure_id": "A"},
             {"tick": 3, "kind": "close", "exposure_id": "A"}],
            [{"tick": 1, "event_id": "x", "value": 5},
             {"tick": 2, "event_id": "y", "value": 9}],
            1,
        )
        evidence_id = self.ingest_document(batch, document)
        artifact, _ = self.reopen().qualification.qualify_release(evidence_id)
        # x at the open tick may fall inside (A latches x) or outside (A latches y).
        self.assertEqual(qualification_signature(artifact),
                         (("A", (("x", 5), ("y", 9)), False, "review"),))

    def test_close_tick_reading_and_seal_witness(self):
        batch = self.station.registry.register("coil-close", SOURCE, ("A",))
        control = [{"tick": 0, "kind": "open", "exposure_id": "A"},
                   {"tick": 2, "kind": "close", "exposure_id": "A"}]
        samples = [{"tick": 2, "event_id": "y", "value": 4}]
        latched = self.ingest_document(batch, boundary_recording(control, samples, 1))
        empty = self.ingest_document(batch, boundary_recording(control, samples, 0))
        # Seal 1 keeps only the order where y precedes the close: A confirmed, not empty.
        artifact, _ = self.reopen().qualification.qualify_release(latched)
        self.assertEqual(qualification_signature(artifact), (("A", (("y", 4),), False, "confirmed"),))
        # Seal 0 keeps only the order where the close precedes y: A stays empty.
        artifact_empty, _ = self.station.qualification.qualify_release(empty)
        self.assertEqual(qualification_signature(artifact_empty), (("A", (), True, "review"),))

    def test_channel_order_kept_for_same_tick_readings(self):
        batch = self.station.registry.register("coil-pair", SOURCE, ("A",))
        document = boundary_recording(
            [{"tick": 0, "kind": "open", "exposure_id": "A"},
             {"tick": 5, "kind": "close", "exposure_id": "A"}],
            [{"tick": 2, "event_id": "x", "value": 1},
             {"tick": 2, "event_id": "y", "value": 2}],
            1,
        )
        evidence_id = self.ingest_document(batch, document)
        artifact, _ = self.reopen().qualification.qualify_release(evidence_id)
        # Same tick inside one window: only the channel-first reading can latch.
        self.assertEqual(qualification_signature(artifact), (("A", (("x", 1),), False, "confirmed"),))
