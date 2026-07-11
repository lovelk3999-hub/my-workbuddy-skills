#!/usr/bin/env python3
"""HAI 实例管理器 — 查状态/开机/关机/查IP

用法:
  python3 haimgr.py status    # 查实例状态 + IP
  python3 haimgr.py start     # 开机
  python3 haimgr.py stop      # 关机
  python3 haimgr.py wait      # 等待开机完成，打印新 IP

配置加载顺序（二选一）:
  1. config.local.json（与本脚本同目录）
     推荐方式，配置持久化到文件，一次填写永久有效。

  2. 环境变量
     HAI_SECRET_ID    — 腾讯云 SecretId
     HAI_SECRET_KEY   — 腾讯云 SecretKey
     HAI_REGION       — 地域（如 ap-shanghai）
     HAI_INSTANCE_ID  — HAI 实例 ID
"""

import json, sys, os, time

# 尝试加载配置
def load_config():
    # 方式1: config.local.json 持久配置
    cfg_path = os.path.join(os.path.dirname(__file__), 'config.local.json')
    if os.path.exists(cfg_path):
        with open(cfg_path) as f:
            return json.load(f)

    # 方式2: 环境变量
    env_keys = ['HAI_SECRET_ID', 'HAI_SECRET_KEY', 'HAI_REGION', 'HAI_INSTANCE_ID']
    env_vals = [os.environ.get(k) for k in env_keys]
    if all(env_vals):
        return {
            'secret_id': env_vals[0],
            'secret_key': env_vals[1],
            'region': env_vals[2],
            'instance_id': env_vals[3],
        }

    # 都没找到 — 输出帮助信息
    print("=" * 60)
    print("  ❌ 未找到 HAI 实例配置")
    print()
    print("  首次使用需要提供以下信息：")
    print()
    print("    SecretId     — 腾讯云 API 密钥 ID")
    print("    SecretKey    — 腾讯云 API 密钥 Key")
    print("    Region       — 地域（如 ap-shanghai）")
    print("    InstanceId   — HAI 实例 ID")
    print()
    print("  请按以下格式提供：")
    print()
    print('    "SecretId: xxx, SecretKey: xxx, Region: xxx, InstanceId: xxx"')
    print()
    print("  AI 会自动写入 config.local.json，后续免填。")
    print("=" * 60)
    sys.exit(1)


cfg = load_config()

# 检查 tencentcloud SDK 是否安装，未安装则输出友好提示
try:
    from tencentcloud.common import credential
    from tencentcloud.hai.v20230812 import hai_client, models
except ModuleNotFoundError:
    print("=" * 60)
    print("  ❌ 缺少 tencentcloud-sdk-python")
    print()
    print("  请先安装：")
    print()
    print("    pip install tencentcloud-sdk-python")
    print()
    print("  安装后重试即可。")
    print("=" * 60)
    sys.exit(1)

cred = credential.Credential(cfg['secret_id'], cfg['secret_key'])
client = hai_client.HaiClient(cred, cfg['region'])
inst_id = cfg['instance_id']


def get_instance():
    req = models.DescribeInstancesRequest()
    req.InstanceIds = [inst_id]
    resp = client.DescribeInstances(req)
    if not resp.InstanceSet:
        print("未找到实例，请检查 InstanceId 是否正确")
        sys.exit(1)
    return resp.InstanceSet[0]


def cmd_status():
    inst = get_instance()
    print(f"实例名称: {inst.InstanceName or '(未命名)'}")
    print(f"实例 ID : {inst.InstanceId}")
    print(f"状态     : {inst.InstanceState}")  # RUNNING / STOPPED
    ips = inst.PublicIpAddresses or []
    if ips:
        print(f"公网 IP : {', '.join(ips)}")
    else:
        print("公网 IP : (无)")


def cmd_start():
    inst = get_instance()
    if inst.InstanceState == 'RUNNING':
        ips = inst.PublicIpAddresses or []
        print(f"实例已在运行，IP: {', '.join(ips) if ips else '无'}")
        return
    req = models.StartInstanceRequest()
    req.InstanceId = inst_id
    client.StartInstance(req)
    print("开机指令已发送，等待实例启动...")


def cmd_stop():
    inst = get_instance()
    if inst.InstanceState == 'STOPPED':
        print("实例已关机")
        return
    req = models.StopInstanceRequest()
    req.InstanceId = inst_id
    client.StopInstance(req)
    print("关机指令已发送")


def cmd_wait():
    print("等待实例启动...")
    for i in range(30):
        inst = get_instance()
        if inst.InstanceState == 'RUNNING':
            ips = inst.PublicIpAddresses or []
            print(f"\n✅ 实例已启动！")
            print(f"   新 IP: {', '.join(ips) if ips else '无'}")
            print(f"   ComfyUI: http://{ips[0]}:6889")
            print(f"   API 服务: http://{ips[0]}:6888")
            return
        print(f"  等待中... ({i+1}/30)", end='\r')
        time.sleep(10)
    print("\n❌ 等待超时，请去控制台检查")


if __name__ == '__main__':
    cmds = {'status': cmd_status, 'start': cmd_start, 'stop': cmd_stop, 'wait': cmd_wait}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print(__doc__)
        sys.exit(1)
    cmds[sys.argv[1]]()
