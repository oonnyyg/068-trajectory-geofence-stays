import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from geofence_report.errors import InputError
from geofence_report.report import build_report

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]
NOTCHED = [[0, 0], [10, 0], [10, 10], [6, 10], [6, 4], [4, 4], [4, 10], [0, 10]]


def make_input(fences, tracks, max_gap=5, threshold=0):
    return {
        "fences": [{"id": fid, "polygon": poly} for fid, poly in fences],
        "trajectories": [{"id": oid, "points": pts} for oid, pts in tracks],
        "max_gap_seconds": max_gap,
        "threshold_seconds": threshold,
    }


def fence_entry(report, oid, fid):
    obj = next(o for o in report["objects"] if o["object_id"] == oid)
    return next(f for f in obj["fences"] if f["fence_id"] == fid)


class GeometryTests(unittest.TestCase):
    def test_concave_polygon_two_intervals(self):
        data = make_input(
            [("notch", NOTCHED)],
            [("obj", [[0, -2, 7], [14, 12, 7]])],
            max_gap=100,
        )
        entry = fence_entry(build_report(data), "obj", "notch")
        self.assertEqual(
            [(iv["start"], iv["end"]) for iv in entry["intervals"]],
            [(2, 6), (8, 12)],
        )
        self.assertEqual(entry["total_seconds"], 8)

    def test_along_edge_counts_as_inside(self):
        data = make_input(
            [("sq", SQUARE)],
            [("obj", [[0, 0, 0], [10, 10, 0]])],
            max_gap=100,
        )
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual([(iv["start"], iv["end"]) for iv in entry["intervals"]], [(0, 10)])
        self.assertEqual(entry["total_seconds"], 10)

    def test_gap_breaks_and_drops_segment(self):
        data = make_input(
            [("sq", SQUARE)],
            [("obj", [[0, 2, 5], [5, 8, 5], [20, 2, 5]])],
            max_gap=5,
        )
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual([(iv["start"], iv["end"]) for iv in entry["intervals"]], [(0, 5)])
        self.assertEqual(entry["total_seconds"], 5)

    def test_threshold_equality_qualifies(self):
        data = make_input(
            [("notch", NOTCHED)],
            [("obj", [[0, -2, 7], [14, 12, 7]])],
            max_gap=100,
            threshold=4,
        )
        entry = fence_entry(build_report(data), "obj", "notch")
        self.assertEqual(len(entry["qualifying_intervals"]), 2)
        data["threshold_seconds"] = 5
        entry = fence_entry(build_report(data), "obj", "notch")
        self.assertEqual(entry["qualifying_intervals"], [])

    def test_zero_duration_touch_not_counted(self):
        data = make_input(
            [("sq", SQUARE)],
            [("obj", [[0, 5, -2], [2, 5, 0], [4, 5, -2]])],
            max_gap=100,
        )
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual(entry["intervals"], [])
        self.assertEqual(entry["total_seconds"], 0)

    def test_single_point_zero_total(self):
        data = make_input([("sq", SQUARE)], [("obj", [[3, 5, 5]])])
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual(entry["intervals"], [])
        self.assertEqual(entry["total_seconds"], 0)

    def test_intervals_merge_across_segments(self):
        data = make_input(
            [("sq", SQUARE)],
            [("obj", [[0, 2, 2], [5, 5, 5], [9, 8, 8]])],
            max_gap=100,
        )
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual([(iv["start"], iv["end"]) for iv in entry["intervals"]], [(0, 9)])

    def test_fractional_crossing_times(self):
        data = make_input(
            [("sq", SQUARE)],
            [("obj", [[0, -1, 5], [3, 11, 5]])],
            max_gap=100,
        )
        entry = fence_entry(build_report(data), "obj", "sq")
        self.assertEqual(entry["intervals"][0]["start"], 0.25)
        self.assertEqual(entry["intervals"][0]["end"], 2.75)
        self.assertAlmostEqual(entry["total_seconds"], 2.5)


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, data, fragment):
        with self.assertRaises(InputError) as ctx:
            build_report(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_duplicate_vertex_rejected(self):
        poly = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
        data = make_input([("sq", poly)], [("o", [[0, 1, 1]])])
        self.assert_invalid(data, "duplicate vertex")

    def test_self_intersection_rejected(self):
        bowtie = [[0, 0], [10, 10], [10, 0], [0, 10]]
        data = make_input([("bad", bowtie)], [("o", [[0, 1, 1]])])
        self.assert_invalid(data, "non-adjacent edges")

    def test_zero_area_rejected(self):
        data = make_input([("bad", [[0, 0], [5, 5], [10, 10]])], [("o", [[0, 1, 1]])])
        self.assert_invalid(data, "area is zero")

    def test_duplicate_timestamp_rejected(self):
        data = make_input([("sq", SQUARE)], [("o", [[0, 1, 1], [0, 2, 2]])])
        self.assert_invalid(data, "duplicate timestamp")

    def test_unsorted_times_rejected(self):
        data = make_input([("sq", SQUARE)], [("o", [[5, 1, 1], [2, 2, 2]])])
        self.assert_invalid(data, "strictly increasing")

    def test_bad_max_gap_rejected(self):
        data = make_input([("sq", SQUARE)], [("o", [[0, 1, 1]])], max_gap=0)
        self.assert_invalid(data, "max_gap_seconds")

    def test_negative_threshold_rejected(self):
        data = make_input([("sq", SQUARE)], [("o", [[0, 1, 1]])], threshold=-1)
        self.assert_invalid(data, "threshold_seconds")

    def test_non_finite_coordinate_rejected(self):
        data = make_input([("sq", SQUARE)], [("o", [[0, float("nan"), 1]])])
        self.assert_invalid(data, "finite")


class CliTests(unittest.TestCase):
    def run_cli(self, data):
        tmp = Path(tempfile.mkdtemp())
        src = tmp / "in.json"
        dst = tmp / "out.json"
        src.write_text(json.dumps(data), encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, "-m", "geofence_report", str(src), str(dst)],
            capture_output=True,
            text=True,
        )
        return proc, dst

    def test_cli_success_writes_report(self):
        data = make_input([("sq", SQUARE)], [("obj", [[0, 2, 2], [4, 8, 8]])], max_gap=10)
        proc, dst = self.run_cli(data)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        report = json.loads(dst.read_text(encoding="utf-8"))
        self.assertIn("interpolation_rule", report)
        self.assertEqual(report["objects"][0]["fences"][0]["total_seconds"], 4)

    def test_cli_error_no_output_file(self):
        data = make_input([("sq", SQUARE)], [("obj", [[0, 1, 1], [0, 2, 2]])])
        proc, dst = self.run_cli(data)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("trajectories[0].points[1]", proc.stderr)
        self.assertFalse(dst.exists())


if __name__ == "__main__":
    unittest.main()
