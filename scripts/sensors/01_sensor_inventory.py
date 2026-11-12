"""第一步：认名字、看真实结构、记录一次查询耗时。"""
from common import connected, entry, imu_summary, lidar_summary, load_sdk, parser, Evidence


def main():
    p = parser(__doc__)
    p.add_argument('--sensor', choices=('imu', 'lidar', 'ultrasonic'), default='imu')
    args = p.parse_args()
    sdk = load_sdk()
    print('SDK 提供的 SensorType（不等于实机硬件清单）：')
    print([name for name in dir(sdk.SensorType) if name.isupper()])
    name = {'imu': args.imu, 'lidar': 'BASE_LIDAR', 'ultrasonic': 'BASE_ULTRASONIC'}[args.sensor]
    evidence = Evidence()
    try:
        with connected(sdk, [name], args.wait) as robot:
            if args.sensor == 'imu':
                getter = lambda: robot.get_imu_data(getattr(sdk.SensorType, name))
                summary = imu_summary
            elif args.sensor == 'lidar':
                getter = lambda: robot.get_lidar_data(sdk.SensorType.BASE_LIDAR)
                summary = lidar_summary
            else:
                from common import ultrasonic_summary
                getter = lambda: robot.get_ultrasonic_data(sdk.UltrasonicType.FRONT_LEFT)
                summary = ultrasonic_summary
            data, _ = evidence.read(name, getter, summary)
            if isinstance(data, dict):
                print('\n实际返回结构（雷达二进制内容省略）：')
                for key, value in data.items():
                    if key == 'data':
                        print(f'{key}: {type(value).__name__}, 长度 {len(value)}')
                    else:
                        print(f'{key}: {value!r}')
            print('\n单次读数不能确认数据更新；下一步使用连续观察脚本。')
    finally:
        evidence.save(args.output, 'inventory')


if __name__ == '__main__':
    entry(main)
