#!/usr/bin/env python3
"""Manage a Tencent Cloud HAI instance and its FLF2V access rules."""

import ipaddress
import json
import sys
import time
from pathlib import Path
from urllib import request

from tencentcloud.common import credential
from tencentcloud.hai.v20230812 import hai_client, models
from tencentcloud.vpc.v20170312 import vpc_client, models as vpc_models


ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "haimgr.json"
VIDEO_PORTS = {"6888", "6889"}
MANAGED_RULE_PREFIX = "HAI FLF2V"


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            "Missing config/haimgr.json. Copy config/haimgr.example.json and fill it locally."
        )
    config = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    missing = [key for key in ("secret_id", "secret_key", "region", "instance_id") if not config.get(key)]
    if missing:
        raise ValueError(f"Missing config keys: {', '.join(missing)}")
    return config


def clients(config):
    cred = credential.Credential(config["secret_id"], config["secret_key"])
    return cred, hai_client.HaiClient(cred, config["region"])


def get_instance(config, client):
    req = models.DescribeInstancesRequest()
    req.InstanceIds = [config["instance_id"]]
    response = client.DescribeInstances(req)
    if not response.InstanceSet:
        raise RuntimeError("HAI instance was not found; check instance_id and region")
    return response.InstanceSet[0]


def public_video_rule_indexes(ingress):
    """Return public 6888/6889 policy indexes that must not remain exposed."""
    return [
        rule["PolicyIndex"]
        for rule in ingress
        if rule.get("Port") in VIDEO_PORTS
        and (rule.get("CidrBlock") == "0.0.0.0/0" or rule.get("Ipv6CidrBlock") == "::/0")
    ]


def http_public_ip():
    return request.urlopen("https://api.ipify.org", timeout=15).read().decode().strip()


def video_access_cidrs(http_ip_getter=http_public_ip):
    """Keep both Tencent API and HTTP-proxy egress paths reachable."""
    cidrs = {"MY_PUBLIC_IP"}
    try:
        address = ipaddress.ip_address(http_ip_getter())
        cidrs.add(f"{address}/{32 if address.version == 4 else 128}")
    except Exception:
        pass
    return sorted(cidrs)


def sync_video_access_rules(config, cred, instance):
    """Restrict ComfyUI and command API access to the current controller."""
    group_ids = instance.SecurityGroupIds or []
    if not group_ids:
        raise RuntimeError("HAI instance has no security group for FLF2V access control")

    vpc = vpc_client.VpcClient(cred, config["region"])
    group_id = group_ids[0]
    describe = vpc_models.DescribeSecurityGroupPoliciesRequest()
    describe.SecurityGroupId = group_id
    ingress = json.loads(vpc.DescribeSecurityGroupPolicies(describe).to_json_string())["SecurityGroupPolicySet"]["Ingress"]

    stale_indexes = set(public_video_rule_indexes(ingress))
    stale_indexes.update(
        rule["PolicyIndex"]
        for rule in ingress
        if rule.get("Port") in VIDEO_PORTS
        and rule.get("PolicyDescription", "").startswith(MANAGED_RULE_PREFIX)
    )

    add_set = vpc_models.SecurityGroupPolicySet()
    add_set.Ingress = []
    for cidr in video_access_cidrs():
        for port in sorted(VIDEO_PORTS):
            policy = vpc_models.SecurityGroupPolicy()
            policy.Protocol = "TCP"
            policy.Port = port
            policy.CidrBlock = cidr
            policy.Action = "ACCEPT"
            policy.PolicyDescription = "HAI FLF2V local automation"
            add_set.Ingress.append(policy)

    create = vpc_models.CreateSecurityGroupPoliciesRequest()
    create.SecurityGroupId = group_id
    create.SecurityGroupPolicySet = add_set
    vpc.CreateSecurityGroupPolicies(create)

    if stale_indexes:
        remove_set = vpc_models.SecurityGroupPolicySet()
        remove_set.Ingress = []
        for index in sorted(stale_indexes):
            policy = vpc_models.SecurityGroupPolicy()
            policy.PolicyIndex = index
            remove_set.Ingress.append(policy)
        delete = vpc_models.DeleteSecurityGroupPoliciesRequest()
        delete.SecurityGroupId = group_id
        delete.SecurityGroupPolicySet = remove_set
        vpc.DeleteSecurityGroupPolicies(delete)

    print("Synchronized ports 6888 and 6889 to the current controller.")


def print_status(instance):
    ips = instance.PublicIpAddresses or []
    print(f"instance: {instance.InstanceName or '(unnamed)'}")
    print(f"instance_id: {instance.InstanceId}")
    print(f"state: {instance.InstanceState}")
    print(f"public_ip: {', '.join(ips) if ips else '(none)'}")


def cmd_status(config, client, cred):
    print_status(get_instance(config, client))


def cmd_start(config, client, cred):
    instance = get_instance(config, client)
    sync_video_access_rules(config, cred, instance)
    if instance.InstanceState == "RUNNING":
        print_status(instance)
        return
    req = models.StartInstanceRequest()
    req.InstanceId = config["instance_id"]
    client.StartInstance(req)
    print("Start request sent.")


def cmd_stop(config, client, cred):
    instance = get_instance(config, client)
    if (instance.InstanceState or "").startswith("STOPPED"):
        print_status(instance)
        return
    req = models.StopInstanceRequest()
    req.InstanceId = config["instance_id"]
    client.StopInstance(req)
    print("Stop request sent.")


def cmd_wait(config, client, cred):
    for attempt in range(30):
        instance = get_instance(config, client)
        if instance.InstanceState == "RUNNING":
            print_status(instance)
            ips = instance.PublicIpAddresses or []
            if ips:
                print(f"comfyui: http://{ips[0]}:6889")
                print(f"command_api: http://{ips[0]}:6888")
            return
        print(f"Waiting for HAI to start ({attempt + 1}/30)...")
        time.sleep(10)
    raise TimeoutError("Timed out waiting for HAI to become RUNNING")


def main(argv=None):
    commands = {"status": cmd_status, "start": cmd_start, "stop": cmd_stop, "wait": cmd_wait}
    args = argv or sys.argv[1:]
    if len(args) != 1 or args[0] not in commands:
        print(f"Usage: {Path(__file__).name} {'|'.join(commands)}", file=sys.stderr)
        return 2
    try:
        config = load_config()
        cred, client = clients(config)
        commands[args[0]](config, client, cred)
        return 0
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
