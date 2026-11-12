"""离线边界测试与模拟 SDK 流程；数据均为合成，不代表实机。"""
import contextlib
import io
import math
import runpy
import struct
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

from common import DIRECTIONS, Evidence, imu_summary, xyz_points


def cloud(big=False):
    # 字段顺序打乱，XYZ 之间有空洞，点跨度 24，行跨度 32。
    raw = bytearray(64)
    endian = '>' if big else '<'
    for row, values in enumerate(((1., 2., 3.), (4., 5., 6.))):
        for offset, value in zip((4, 12, 16), values):
            struct.pack_into(endian + 'f', raw, row * 32 + offset, value)
    return dict(width=1, height=2, point_step=24, row_step=32,
                fields=[dict(name=axis, offset=offset, datatype=7, count=1)
                        for axis, offset in zip(('z', 'x', 'y'), (16, 4, 12))],
                is_bigendian=big, data=bytes(raw), timestamp_ns=10)


class OfflineTests(unittest.TestCase):
    def test_padding_and_byte_order(self):
        for big in (False, True):
            self.assertEqual(xyz_points(cloud(big)), [(1., 2., 3.), (4., 5., 6.)])

    def test_truncation_and_bad_offset(self):
        c = cloud()
        c['data'] = c['data'][:-1]
        with self.assertRaises(ValueError):
            xyz_points(c)
        c = cloud()
        c['fields'][0]['offset'] = 23
        with self.assertRaises(ValueError):
            xyz_points(c)

    def test_nonfinite_filtered(self):
        c = cloud()
        raw = bytearray(c['data'])
        struct.pack_into('<f', raw, 4, math.nan)
        c['data'] = raw
        self.assertEqual(xyz_points(c), [(4., 5., 6.)])

    def test_missing_imu_is_not_zero(self):
        summary = imu_summary({'accel': {'x': 0, 'y': 0}})
        self.assertIsNone(summary['accel'])
        self.assertIsNone(summary['gyro_norm'])

    def test_timestamp_evidence(self):
        for stamps, expected in (((10, 10), 'WARN'), ((10, 11), 'OBSERVED'),
                                 ((11, 10), 'WARN'), ((None, None), 'WARN'),
                                 ((10, 10, 11), 'OBSERVED')):
            evidence = Evidence()
            evidence.rows = [{'sensor': 'a', 'timestamp_ns': t} for t in stamps]
            self.assertEqual(evidence.verdicts()[0][1], expected)
        evidence.rows = [{'sensor': 'a', 'error': 'empty'}]
        self.assertEqual(evidence.verdicts()[0][1], 'FAIL')

    def test_each_script_with_fake_sdk(self):
        sdk = types.ModuleType('galbot_sdk.g1')
        sdk.SensorType = types.SimpleNamespace(**{name: name for name in
            ('TORSO_IMU', 'CHASSIS_IMU', 'LIDAR_IMU', 'BASE_LIDAR', 'BASE_ULTRASONIC')})
        sdk.UltrasonicType = types.SimpleNamespace(**{name: name for name in DIRECTIONS})
        instances = []

        class FakeRobot:
            def __init__(self):
                self.counter = 0
                self.cleaned = []
                instances.append(self)

            def init(self, enabled):
                self.enabled = enabled
                return True

            def stamp(self):
                self.counter += 1
                return self.counter * 100000000

            def get_imu_data(self, name):
                assert name in self.enabled
                return dict(timestamp_ns=self.stamp(), accel=dict(x=0, y=0, z=9.81),
                            gyro=dict(x=0, y=0, z=0))

            def get_lidar_data(self, name):
                assert name in self.enabled
                c = cloud()
                c['timestamp_ns'] = self.stamp()
                return c

            def get_ultrasonic_data(self, name):
                assert 'BASE_ULTRASONIC' in self.enabled
                return dict(timestamp_ns=self.stamp(), distance=1.)

            def request_shutdown(self):
                self.cleaned.append('request')

            def wait_for_shutdown(self):
                self.cleaned.append('wait')

            def destroy(self):
                self.cleaned.append('destroy')

        sdk.GalbotRobot = FakeRobot
        parent = types.ModuleType('galbot_sdk')
        parent.g1 = sdk
        scripts = sorted(Path(__file__).parent.glob('0*.py'))
        with tempfile.TemporaryDirectory() as output:
            with patch.dict(sys.modules, {'galbot_sdk': parent, 'galbot_sdk.g1': sdk}), \
                 patch('time.sleep'), contextlib.redirect_stdout(io.StringIO()):
                for script in scripts:
                    argv = [str(script), '--samples', '2', '--output', output]
                    with patch.object(sys, 'argv', argv):
                        runpy.run_path(str(script), run_name='__main__')
            self.assertEqual(len(list(Path(output).glob('*/report.md'))), 5)
            self.assertEqual(len(list(Path(output).glob('*/last_frame.ply'))), 1)
            for robot in instances:
                self.assertEqual(robot.cleaned, ['request', 'wait', 'destroy'])


if __name__ == '__main__':
    unittest.main()
