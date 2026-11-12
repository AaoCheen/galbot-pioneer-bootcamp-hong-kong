"""第四步：按枚举名称观察八方向距离，不猜测安装顺序。"""
import time
from common import connected, DIRECTIONS, entry, load_sdk, parser, ultrasonic_summary, Evidence


def main():
    args = parser(__doc__).parse_args()
    sdk = load_sdk()
    evidence = Evidence()
    print('可在安全间距外移动纸板，比较各方向读数；不要触碰或推动机器人。')
    print('0、负值、无穷值可能是无回波/无效约定，需查实机定义，不能当作无障碍。')
    try:
        with connected(sdk, ['BASE_ULTRASONIC'], args.wait) as robot:
            for i in range(args.samples):
                for name in DIRECTIONS:
                    evidence.read(name, lambda n=name: robot.get_ultrasonic_data(getattr(sdk.UltrasonicType, n)), ultrasonic_summary)
                if i + 1 < args.samples:
                    time.sleep(args.interval)
    finally:
        evidence.save(args.output, 'ultrasonic')


if __name__ == '__main__':
    entry(main)
