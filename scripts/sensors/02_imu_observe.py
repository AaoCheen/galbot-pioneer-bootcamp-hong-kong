"""第二步：观察加速度、角速度与时间戳，记录静止基线。"""
import statistics
import time
from common import connected, entry, imu_summary, load_sdk, parser, Evidence


def main():
    args = parser(__doc__).parse_args()
    sdk = load_sdk()
    evidence = Evidence()
    print('保持机器人静止；accel_norm 是三轴加速度模长，不是 Z 轴。')
    print('含重力且单位为 m/s² 时，静止模长通常约 9.81；安装方向决定分量。')
    try:
        with connected(sdk, [args.imu], args.wait) as robot:
            for i in range(args.samples):
                evidence.read(args.imu, lambda: robot.get_imu_data(getattr(sdk.SensorType, args.imu)), imu_summary)
                if i + 1 < args.samples:
                    time.sleep(args.interval)
        # 统计唯一时间戳，避免重复缓存把静止噪声估计压低。
        unique = {r['timestamp_ns']: r for r in evidence.rows if r.get('timestamp_ns') and 'error' not in r}
        for key in ('accel_norm', 'gyro_norm'):
            values = [r[key] for r in unique.values() if r.get(key) is not None]
            if len(values) >= 2:
                print(f'{key}: 唯一时间戳样本 {len(values)}, 均值 {statistics.mean(values):.6f}, '
                      f'样本标准差 {statistics.stdev(values):.6f}, min/max {min(values):.6f}/{max(values):.6f}')
        print('这里没有计算姿态角或位移；magnet 字段存在也不证明磁力计有效。')
    finally:
        evidence.save(args.output, 'imu')


if __name__ == '__main__':
    entry(main)
