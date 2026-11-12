"""探索脚本共用工具；SDK 延迟导入，Mac 上也能查看 --help。"""
import argparse
import json
import math
import struct
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

DIRECTIONS = ('FRONT_LEFT', 'FRONT_RIGHT', 'RIGHT_LEFT', 'RIGHT_RIGHT',
              'BACK_LEFT', 'BACK_RIGHT', 'LEFT_LEFT', 'LEFT_RIGHT')
IMUS = ('TORSO_IMU', 'CHASSIS_IMU', 'LIDAR_IMU')


def positive(value):
    number = float(value)
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('必须是有限正数')
    return number


def count(value):
    number = int(value)
    if number < 2:
        raise argparse.ArgumentTypeError('至少读取 2 次，以便比较时间戳')
    return number


def parser(description):
    p = argparse.ArgumentParser(description=description)
    p.add_argument('--imu', choices=IMUS, default='TORSO_IMU', help='显式选择 IMU，不自动替换')
    p.add_argument('--samples', type=count, default=10, help='采样轮数，默认 10')
    p.add_argument('--interval', type=positive, default=0.5, help='两轮之间等待秒数，不是驱动频率')
    p.add_argument('--wait', type=positive, default=3, help='初始化后等待秒数')
    p.add_argument('--output', type=Path, default=Path(__file__).parent / 'output', help='结果根目录')
    return p


def load_sdk():
    try:
        import galbot_sdk.g1 as sdk
    except ImportError as exc:
        raise RuntimeError('请在 HPU 上已配置的 G1 SDK Python 环境运行；本机可用 --help。') from exc
    return sdk


@contextmanager
def connected(sdk, names, wait):
    # 枚举存在只说明软件支持，不证明实机装有或正在发布该传感器。
    missing = [name for name in names if not hasattr(sdk.SensorType, name)]
    if missing:
        raise RuntimeError('当前 SDK 缺少枚举：' + ', '.join(missing))
    robot = sdk.GalbotRobot()
    try:
        started = time.perf_counter()
        if not robot.init({getattr(sdk.SensorType, name) for name in names}):
            raise RuntimeError('SDK 初始化失败，请核对环境、服务和传感器枚举。')
        print(f'init 耗时 {time.perf_counter() - started:.3f} s；启用 {names}')
        time.sleep(wait)
        yield robot
    finally:
        # 即使初始化中途失败，也逐项尝试官方的资源释放流程。
        for method in ('request_shutdown', 'wait_for_shutdown', 'destroy'):
            try:
                getattr(robot, method)()
            except Exception as exc:
                print(f'资源释放 {method} 异常：{exc!r}')


def timestamp(data):
    if not isinstance(data, dict):
        return None
    stamp = data.get('timestamp_ns')
    if stamp is None and isinstance(data.get('header'), dict):
        stamp = data['header'].get('timestamp_ns')
    return stamp if isinstance(stamp, int) and not isinstance(stamp, bool) and stamp > 0 else None


def vector(data, key):
    values = data.get(key) if isinstance(data, dict) else None
    if not isinstance(values, dict):
        return None
    xyz = [values.get(axis) for axis in 'xyz']
    if not all(isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v) for v in xyz):
        return None
    return xyz


def norm(xyz):
    return math.sqrt(sum(v * v for v in xyz)) if xyz is not None else None


def imu_summary(data):
    accel, gyro = vector(data, 'accel'), vector(data, 'gyro')
    return {'accel': accel, 'accel_norm': norm(accel), 'gyro': gyro,
            'gyro_norm': norm(gyro), 'magnet': vector(data, 'magnet')}


def xyz_points(cloud):
    """按 PointCloud2 的 offset/point_step/row_step/字节序解析，不假设紧密排列。"""
    width, height = int(cloud['width']), int(cloud['height'])
    step, row = int(cloud['point_step']), int(cloud['row_step'])
    if width < 0 or height < 0 or step <= 0 or row < width * step:
        raise ValueError('非法点云尺寸或跨度')
    raw = bytes(cloud['data'])
    if len(raw) < height * row:
        raise ValueError(f'点云数据截断：{len(raw)} < {height * row}')
    types = {1: 'b', 2: 'B', 3: 'h', 4: 'H', 5: 'i', 6: 'I', 7: 'f', 8: 'd'}
    endian = '>' if cloud['is_bigendian'] else '<'
    fields = {field['name']: field for field in cloud['fields']}
    readers = []
    for axis in 'xyz':
        f = fields.get(axis)
        if f is None or f.get('count') != 1 or f.get('datatype') not in types:
            raise ValueError(f'{axis} 字段缺失或类型/count 不受支持')
        reader = struct.Struct(endian + types[f['datatype']])
        offset = int(f['offset'])
        if offset < 0 or offset + reader.size > step:
            raise ValueError(f'{axis} offset 越界')
        readers.append((offset, reader))
    points = []
    for y in range(height):
        for x in range(width):
            base = y * row + x * step
            point = tuple(reader.unpack_from(raw, base + offset)[0] for offset, reader in readers)
            if all(math.isfinite(v) for v in point):
                points.append(point)
    return points


def lidar_summary(data):
    points = xyz_points(data)
    n = int(data['width']) * int(data['height'])
    ranges = [norm(p) for p in points]
    return {'declared_points': n, 'finite_xyz': len(points),
            'nonzero_xyz': sum(r > 0 for r in ranges),
            'nearest_nonzero_m': min((r for r in ranges if r > 0), default=None),
            'farthest_m': max(ranges, default=None)}


def ultrasonic_summary(data):
    distance = data.get('distance')
    valid = isinstance(distance, (int, float)) and not isinstance(distance, bool) and math.isfinite(distance)
    return {'distance_m': distance if valid else None,
            'positive_distance': valid and distance > 0}


class Evidence:
    """记录观测证据；缺字段不会当作零，缺时间戳不会声称更新正常。"""
    def __init__(self):
        self.rows = []

    def read(self, name, getter, summarizer):
        start = time.perf_counter()
        row = {'sensor': name, 'host_monotonic_s': start}
        data = None
        try:
            data = getter()
            row['read_ms'] = (time.perf_counter() - start) * 1000
            row['timestamp_ns'] = timestamp(data)
            if not isinstance(data, dict) or not data:
                raise ValueError('未返回非空 dict')
            row.update(summarizer(data))
        except Exception as exc:
            row['error'] = repr(exc)
        self.rows.append(row)
        print(json.dumps(row, ensure_ascii=False, allow_nan=False))
        return data, row

    def verdicts(self):
        results = []
        for name in sorted({r['sensor'] for r in self.rows}):
            rows = [r for r in self.rows if r['sensor'] == name]
            good = [r for r in rows if 'error' not in r]
            stamps = [r.get('timestamp_ns') for r in good]
            reasons = []
            if len(good) != len(rows):
                reasons.append(f'{len(rows)-len(good)}/{len(rows)} 次读取或解析失败')
            if len(stamps) < 2 or any(s is None for s in stamps):
                reasons.append('时间戳不足，无法确认更新')
            elif any(b < a for a, b in zip(stamps, stamps[1:])):
                reasons.append('时间戳回退')
            elif not any(b > a for a, b in zip(stamps, stamps[1:])):
                reasons.append('未观察到时间戳推进（可能重复缓存）')
            if any('accel_norm' in r and (r['accel_norm'] is None or r['gyro_norm'] is None or r['accel_norm'] == 0) for r in good):
                reasons.append('加速度/角速度缺失、非有限或加速度模长为零')
            if any('finite_xyz' in r and (r['finite_xyz'] == 0 or r['nonzero_xyz'] == 0) for r in good):
                reasons.append('没有有限且非零的 XYZ 点')
            if any('positive_distance' in r and not r['positive_distance'] for r in good):
                reasons.append('距离缺失、非有限或非正；需核对无回波约定')
            state = 'FAIL' if not good else ('WARN' if reasons else 'OBSERVED')
            results.append((name, state, '；'.join(reasons) or '观察到可解析数据和时间戳推进；未验证标定精度及绝对新鲜度'))
        return results

    def save(self, root, label):
        # 每次独立目录，避免不同实验相互覆盖。
        directory = root / (datetime.now().strftime('%Y%m%d_%H%M%S_%f') + '_' + label)
        directory.mkdir(parents=True)
        with (directory / 'readings.jsonl').open('w', encoding='utf-8') as f:
            for row in self.rows:
                f.write(json.dumps(row, ensure_ascii=False, allow_nan=False) + '\n')
        lines = ['# 传感器探索观测报告', '', f'实验：{label}', '',
                 '自动记录来自本次调用。OBSERVED 仅代表读数可解析且时间戳曾推进，不代表硬件完全健康。', '',
                 '| 传感器 | 结果 | 证据/待查 |', '|---|---|---|']
        for name, state, detail in self.verdicts():
            print(f'{state}: {name}: {detail}')
            lines.append(f'| {name} | {state} | {detail} |')
        lines += ['', '## 我的观察', '', '- 场景/物体/机器人是否静止：',
                  '- 预测会发生什么：', '- 实际变化及可能原因：', '- 尚不能确定的结论：',
                  '', '轮询速度不等于驱动发布频率；顺序读取不等于同步采样。时间戳时钟域未核实，未计算绝对数据年龄。']
        (directory / 'report.md').write_text('\n'.join(lines) + '\n', encoding='utf-8')
        print(f'结果目录：{directory.resolve()}')
        return directory


def entry(main):
    try:
        main()
    except KeyboardInterrupt:
        print('\n用户中断；正在退出。')
        raise SystemExit(130)
    except Exception as exc:
        print(f'错误：{exc}')
        raise SystemExit(1)
