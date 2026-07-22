"""Unit tests for the CSV reader."""
import unittest
from datetime import datetime
from pathlib import Path

from dpf_doctor.io.reader import parse_trip_start, read_trip

FIXTURES = Path(__file__).resolve().parent / "fixtures"
SAMPLE = FIXTURES / "sample_data" / "2026-06-23 10-26-50.csv"


class TestParseTripStart(unittest.TestCase):
    def test_valid_filename(self):
        self.assertEqual(
            parse_trip_start("data/2026-06-23 10-26-50.csv"),
            datetime(2026, 6, 23, 10, 26, 50),
        )

    def test_basename_only(self):
        self.assertEqual(
            parse_trip_start("2026-06-23 10-26-50.csv"),
            datetime(2026, 6, 23, 10, 26, 50),
        )

    def test_bad_filename_returns_none(self):
        self.assertIsNone(parse_trip_start("random-name.csv"))


class TestReadTrip(unittest.TestCase):
    def test_shipped_sample(self):
        trip = read_trip(str(SAMPLE))
        self.assertIsNotNone(trip)
        self.assertEqual(trip.path, "2026-06-23 10-26-50.csv")
        self.assertEqual(trip.start, datetime(2026, 6, 23, 10, 26, 50))
        self.assertGreater(trip.duration_s, 0)
        # Sample is known to include soot trigger and DPF dp.
        self.assertIn("soot_trig", trip.series)
        self.assertIn("dpf_dp", trip.series)

    def test_series_is_sorted_by_time(self):
        trip = read_trip(str(SAMPLE))
        for key, points in trip.series.items():
            ts = [t for t, _ in points]
            self.assertEqual(ts, sorted(ts), f"series {key!r} not sorted")

    def test_nonexistent_file_raises(self):
        with self.assertRaises(FileNotFoundError):
            read_trip("/does/not/exist.csv")
