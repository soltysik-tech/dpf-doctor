"""Unit tests for the PID registry."""
import unittest

from dpf_doctor import pids


class TestClassify(unittest.TestCase):
    def test_dpf_dp(self):
        self.assertEqual(pids.classify("DPF differential pressure"), "dpf_dp")

    def test_soot_trigger(self):
        self.assertEqual(pids.classify("DPF/GPF soot trigger [%]"), "soot_trig")

    def test_rpm_x1000_wins_over_rpm(self):
        # Longer overlapping needle must be registered first so the x1000 variant
        # doesn't fall through to the bare "Engine RPM" key.
        self.assertEqual(pids.classify("Engine RPM x1000"), "rpm_k")
        self.assertEqual(pids.classify("Engine RPM"), "rpm")

    def test_avg_distance_between_regens(self):
        self.assertEqual(pids.classify("Average Distance Between PF Regens"), "avg_d_regen")

    def test_avg_time_between_regens(self):
        self.assertEqual(pids.classify("Average Time Between PF Regens"), "avg_t_regen")

    def test_unknown_pid_returns_none(self):
        self.assertIsNone(pids.classify("Some Vendor Specific Nonsense"))


class TestUnitOf(unittest.TestCase):
    def test_dp_kpa(self):
        self.assertEqual(pids.unit_of("dpf_dp"), "kPa")

    def test_soot_percent(self):
        self.assertEqual(pids.unit_of("soot_trig"), "%")

    def test_unknown_key(self):
        self.assertIsNone(pids.unit_of("not_a_real_key"))
