"""第五步：同时启用三类传感器，逐项读取，汇总观测证据。"""
import time
from common import (connected, DIRECTIONS, entry, imu_summary, lidar_summary,
                    load_sdk, parser, ultrasonic_summary, Evidence)


def sensor_health_check(robot, sdk, imu, samples, interval, evidence):
    """顺序轮询，不声称同步；单个传感器失败仍继续检查其余项。"""
    for i in range(samples):
        evidence.read(imu, lambda: robot.get_imu_data(getattr(sdk.SensorType, imu)), imu_summary)
        evidence.read('BASE_LIDAR', lambda: robot.get_lidar_data(sdk.SensorType.BASE_LIDAR), lidar_summary)
        for name in DIRECTIONS:
            evidence.read(name, lambda n=name: robot.get_ultrasonic_data(getattr(sdk.UltrasonicType, n)), ultrasonic_summary)
        if i + 1 < samples:
            time.sleep(interval)
    return evidence.verdicts()


def main():
    args = parser(__doc__).parse_args()
    sdk = load_sdk()
    evidence = Evidence()
    try:
        with connected(sdk, [args.imu, 'BASE_LIDAR', 'BASE_ULTRASONIC'], args.wait) as robot:
            results = sensor_health_check(robot, sdk, args.imu, args.samples, args.interval, evidence)
    finally:
        evidence.save(args.output, 'health')
    if any(state != 'OBSERVED' for _, state, _ in results):
        raise SystemExit(2)  # 便于命令行识别待排查项，不是硬件故障码。


if __name__ == '__main__':
    entry(main)
