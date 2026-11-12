"""第三步：解析点云布局，观察距离分布，保存一帧 XYZ。"""
import time
from common import connected, entry, lidar_summary, load_sdk, parser, xyz_points, Evidence


def main():
    args = parser(__doc__).parse_args()
    sdk = load_sdk()
    evidence = Evidence()
    last = None
    print('距离均相对点云原点，不是距机器人外壳距离；不用于直接避障。')
    try:
        with connected(sdk, ['BASE_LIDAR'], args.wait) as robot:
            for i in range(args.samples):
                cloud, row = evidence.read('BASE_LIDAR', lambda: robot.get_lidar_data(sdk.SensorType.BASE_LIDAR), lidar_summary)
                if 'error' not in row:
                    last = cloud
                    if i == 0:
                        print('fields =', cloud['fields'])
                        print('point_step / row_step =', cloud['point_step'], cloud['row_step'])
                if i + 1 < args.samples:
                    time.sleep(args.interval)
    finally:
        directory = evidence.save(args.output, 'lidar')
        if last is not None:
            points = xyz_points(last)
            # 纯文本 PLY 可在 CloudCompare / MeshLab 中打开。
            with (directory / 'last_frame.ply').open('w', encoding='ascii') as f:
                f.write('ply\nformat ascii 1.0\n' + f'element vertex {len(points)}\n'
                        + 'property float x\nproperty float y\nproperty float z\nend_header\n')
                for x, y, z in points:
                    f.write(f'{x:.7g} {y:.7g} {z:.7g}\n')
            print('已保存最后成功帧：last_frame.ply；仅含有限 XYZ，未做坐标变换。')


if __name__ == '__main__':
    entry(main)
