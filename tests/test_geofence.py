import json
import os
import subprocess
import sys
import tempfile
import unittest

from geofence_report.core import InputError, build_report

SQUARE = [[0, 0], [10, 0], [10, 10], [0, 10]]
# Concave "U" opening upward: two arms at x in [0,1] and [3,4], y in [0,4].
U_SHAPE = [[0, 0], [4, 0], [4, 4], [3, 4], [3, 1], [1, 1], [1, 4], [0, 4]]


def make_input(points, fence=None, max_gap=60, min_stay=0):
    return {
        "max_gap_seconds": max_gap,
        "min_stay_seconds": min_stay,
        "fences": [{"id": "f1", "vertices": fence or SQUARE}],
        "trajectories": [{"object_id": "obj", "points": points}],
    }


def pts(*rows):
    return [{"t": t, "x": x, "y": y} for t, x, y in rows]


def fence_entry(report, obj="obj", fence="f1"):
    for o in report["objects"]:
        if o["object_id"] == obj:
            for f in o["fences"]:
                if f["fence_id"] == fence:
                    return f
    raise AssertionError("entry not found")


class StayIntervalTests(unittest.TestCase):
    def test_concave_polygon_crossing(self):
        # Straight line y=2 from x=-1 to x=5 in 6s crosses the U shape,
        # producing two separate inside intervals [1,2] and [4,5].
        report = build_report(make_input(pts((0, -1, 2), (6, 5, 2)),
                                         fence=U_SHAPE))
        entry = fence_entry(report)
        got = [(iv["start"], iv["end"]) for iv in entry["intervals"]]
        self.assertEqual(got, [(1.0, 2.0), (4.0, 5.0)])
        self.assertAlmostEqual(entry["total_seconds"], 2.0)

    def test_endpoints_outside_middle_inside(self):
        # Both endpoints outside the square; containment must come from
        # segment clipping, not endpoint tests.
        report = build_report(make_input(pts((0, -5, 5), (20, 15, 5))))
        entry = fence_entry(report)
        got = [(iv["start"], iv["end"]) for iv in entry["intervals"]]
        self.assertEqual(got, [(5.0, 15.0)])

    def test_along_edge_movement(self):
        # Moving along the boundary edge y=0 counts as inside.
        report = build_report(make_input(pts((0, 0, 0), (10, 10, 0))))
        entry = fence_entry(report)
        got = [(iv["start"], iv["end"]) for iv in entry["intervals"]]
        self.assertEqual(got, [(0.0, 10.0)])
        self.assertAlmostEqual(entry["total_seconds"], 10.0)

    def test_zero_duration_touch_ignored(self):
        # Tangent to the corner (0,0) at t=1 only: no stay interval.
        report = build_report(make_input(pts((0, -1, -1), (1, 0, 0),
                                             (2, -1, 1))))
        entry = fence_entry(report)
        self.assertEqual(entry["intervals"], [])
        self.assertEqual(entry["total_seconds"], 0.0)

    def test_gap_breaks_interval(self):
        report = build_report(make_input(
            pts((0, 2, 2), (10, 4, 4), (100, 6, 6), (110, 8, 8)),
            max_gap=60))
        entry = fence_entry(report)
        got = [(iv["start"], iv["end"]) for iv in entry["intervals"]]
        self.assertEqual(got, [(0.0, 10.0), (100.0, 110.0)])
        self.assertAlmostEqual(entry["total_seconds"], 20.0)

    def test_adjacent_segments_merge(self):
        report = build_report(make_input(pts((0, 2, 2), (5, 5, 5),
                                             (10, 8, 8))))
        entry = fence_entry(report)
        got = [(iv["start"], iv["end"]) for iv in entry["intervals"]]
        self.assertEqual(got, [(0.0, 10.0)])

    def test_threshold_equality_included(self):
        report = build_report(make_input(pts((0, 2, 2), (10, 8, 8)),
                                         min_stay=10))
        entry = fence_entry(report)
        self.assertEqual(len(entry["qualifying_intervals"]), 1)
        report = build_report(make_input(pts((0, 2, 2), (10, 8, 8)),
                                         min_stay=11))
        entry = fence_entry(report)
        self.assertEqual(entry["qualifying_intervals"], [])

    def test_single_point_zero_total(self):
        report = build_report(make_input(pts((0, 5, 5))))
        entry = fence_entry(report)
        self.assertEqual(entry["intervals"], [])
        self.assertEqual(entry["total_seconds"], 0.0)

    def test_sorting_by_object_fence_start(self):
        data = {
            "max_gap_seconds": 60,
            "fences": [{"id": "b", "vertices": SQUARE},
                       {"id": "a", "vertices": SQUARE}],
            "trajectories": [
                {"object_id": "z", "points": pts((0, 1, 1), (1, 2, 2))},
                {"object_id": "a", "points": pts((0, 1, 1), (1, 2, 2))},
            ],
        }
        report = build_report(data)
        self.assertEqual([o["object_id"] for o in report["objects"]],
                         ["a", "z"])
        self.assertEqual([f["fence_id"] for f in report["objects"][0]["fences"]],
                         ["a", "b"])


class ValidationTests(unittest.TestCase):
    def assert_invalid(self, data, fragment):
        with self.assertRaises(InputError) as ctx:
            build_report(data)
        self.assertIn(fragment, str(ctx.exception))

    def test_duplicate_vertex_rejected(self):
        bad = [[0, 0], [10, 0], [10, 10], [0, 0]]
        self.assert_invalid(make_input(pts((0, 1, 1)), fence=bad),
                            "duplicate vertex")

    def test_self_intersecting_polygon_rejected(self):
        bowtie = [[0, 0], [10, 10], [10, 0], [0, 10]]
        self.assert_invalid(make_input(pts((0, 1, 1)), fence=bowtie),
                            "intersect")

    def test_zero_area_rejected(self):
        line = [[0, 0], [1, 1], [2, 2]]
        self.assert_invalid(make_input(pts((0, 1, 1)), fence=line),
                            "area is zero")

    def test_duplicate_timestamp_rejected(self):
        self.assert_invalid(make_input(pts((0, 1, 1), (0, 2, 2))),
                            "strictly increasing")

    def test_unsorted_times_rejected(self):
        self.assert_invalid(make_input(pts((5, 1, 1), (2, 2, 2))),
                            "strictly increasing")

    def test_non_finite_coordinate_rejected(self):
        self.assert_invalid(make_input(pts((0, float("nan"), 1))),
                            "finite number")
        self.assert_invalid(
            make_input(pts((0, 1, 1)),
                       fence=[[0, 0], [10, 0], [float("inf"), 10]]),
            "finite number")

    def test_bad_max_gap_rejected(self):
        for bad in (0, -3, 1.5, "10", True):
            self.assert_invalid(make_input(pts((0, 1, 1)), max_gap=bad),
                                "max_gap_seconds")

    def test_bad_threshold_rejected(self):
        self.assert_invalid(make_input(pts((0, 1, 1)), min_stay=-1),
                            "min_stay_seconds")

    def test_error_path_locatable(self):
        data = make_input(pts((0, 1, 1), (0, 2, 2)))
        try:
            build_report(data)
        except InputError as exc:
            self.assertIn("$.trajectories[0].points[1].t", str(exc))
        else:
            self.fail("expected InputError")


class CliTests(unittest.TestCase):
    def run_cli(self, data):
        tmp = tempfile.mkdtemp()
        in_path = os.path.join(tmp, "in.json")
        out_path = os.path.join(tmp, "out.json")
        with open(in_path, "w", encoding="utf-8") as fh:
            json.dump(data, fh)
        proc = subprocess.run(
            [sys.executable, "-m", "geofence_report", in_path, out_path],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        return proc, out_path

    def test_cli_success_writes_report(self):
        proc, out_path = self.run_cli(make_input(pts((0, 2, 2), (10, 8, 8))))
        self.assertEqual(proc.returncode, 0, proc.stderr)
        with open(out_path, encoding="utf-8") as fh:
            report = json.load(fh)
        entry = report["objects"][0]["fences"][0]
        self.assertEqual(entry["total_seconds"], 10.0)
        self.assertIn("linear", report["interpolation"])

    def test_cli_invalid_input_no_output_file(self):
        proc, out_path = self.run_cli(make_input(pts((0, 1, 1), (0, 2, 2))))
        self.assertEqual(proc.returncode, 1)
        self.assertIn("strictly increasing", proc.stderr)
        self.assertFalse(os.path.exists(out_path))

    def test_cli_missing_file(self):
        tmp = tempfile.mkdtemp()
        proc = subprocess.run(
            [sys.executable, "-m", "geofence_report",
             os.path.join(tmp, "nope.json"), os.path.join(tmp, "out.json")],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(os.path.exists(os.path.join(tmp, "out.json")))


if __name__ == "__main__":
    unittest.main()
