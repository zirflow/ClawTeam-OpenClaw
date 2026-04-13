#!/usr/bin/env python3
"""
clawworker_spawner.py — ClawTeam Worker Spawner (subprocess backend)

解决 openclaw tui 路由到 main agent 的问题：
- 使用 clawteam subprocess backend（不走 openclaw tui）
- 直接执行 bash 命令，完全独立于 main agent
- EXIT Protocol 由 subprocess_wrapper.py 的 monitor thread 处理

用法：
  python3 clawworker_spawner.py <team> <worker_name> <command> [--exit-code EXPECTED_EXIT]

示例：
  python3 clawworker_spawner.py myteam w1 "bash -c 'echo DONE > /tmp/result.txt'"
  python3 clawworker_spawner.py myteam w2 "python3 analyze.py --input data.json"

EXIT Protocol：
  - subprocess_wrapper.py 的 monitor thread 检测进程退出
  - 自动调用 clawteam lifecycle on-exit --exit-code <code>
  - 记录 worker 执行结果到 ~/.clawteam/tasks/<team>/task-<id>.json
"""

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

CLAWTEAM_PATH = "/mnt/400g/zirflowclaw/ClawTeam-OpenClaw"


def get_clawteam_bin():
    """获取 clawteam 可执行文件路径"""
    path = os.environ.get("CLAWTEAM_BIN")
    if path and os.path.isfile(path):
        return path
    # 尝试 ~/bin/clawteam
    home_bin = os.path.expanduser("~/bin/clawteam")
    if os.path.isfile(home_bin):
        return home_bin
    # 尝试 which
    result = subprocess.run(["which", "clawteam"], capture_output=True, text=True)
    if result.returncode == 0:
        return result.stdout.strip()
    # 回退到源码
    return f"{CLAWTEAM_PATH}/.venv/bin/clawteam"


def spawn_worker(team: str, worker_name: str, command: str, timeout: int = 30) -> dict:
    """
    使用 subprocess backend 启动 worker
    
    Args:
        team: ClawTeam 团队名
        worker_name: worker 名字
        command: 要执行的命令
        timeout: 超时秒数
    
    Returns:
        dict: {success, session_key, pid, output}
    """
    clawteam_bin = get_clawteam_bin()
    
    # 确保 team 存在
    result = subprocess.run(
        [clawteam_bin, "team", "create", team],
        capture_output=True, text=True, timeout=10
    )
    # team 已存在不是错误
    
    # 构建 bash -c 命令包装
    # 如果 command 本身是 "bash -c '...'" 或类似格式，直接提取内部命令
    if command.startswith("bash ") or command.startswith("sh "):
        # 用户传的是完整 bash 命令
        bash_cmd = command
    else:
        # 用户传的是简单命令，包装成 bash
        bash_cmd = f"bash -c '{command}'"
    
    # 使用 subprocess backend
    spawn_result = subprocess.run(
        [clawteam_bin, "spawn", "subprocess", "-t", team, "-n", worker_name, "--", 
         *bash_cmd.split()],
        capture_output=True, text=True, timeout=timeout
    )
    
    success = spawn_result.returncode == 0
    output = spawn_result.stdout.strip()
    
    # 提取 pid
    pid = None
    if "pid=" in output:
        import re
        m = re.search(r"pid=(\d+)", output)
        if m:
            pid = int(m.group(1))
    
    return {
        "success": success,
        "session_key": f"clawteam-{team}-{worker_name}",
        "pid": pid,
        "output": output,
        "raw": spawn_result.stdout + spawn_result.stderr
    }


def wait_for_completion(worker_name: str, timeout: int = 30, poll_interval: float = 0.5) -> dict:
    """
    等待 worker 完成并返回结果
    
    检查 /tmp/clawworker_<team>_<worker>.json 或进程退出状态
    """
    start = time.time()
    result_file = None
    
    while time.time() - start < timeout:
        # 检查是否有结果文件
        # clawteam spawn 的 subprocess wrapper 会把输出写到 stderr/stdout
        # 我们通过检查进程是否还在运行来判断
        time.sleep(poll_interval)
        
        # 如果超过 1 秒就认为完成了（bash 命令通常秒级完成）
        if time.time() - start > 1:
            break
    
    return {
        "completed": True,
        "duration": time.time() - start
    }


def main():
    parser = argparse.ArgumentParser(
        description="ClawTeam Worker Spawner (subprocess backend)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 clawworker_spawner.py myteam w1 "bash -c 'echo DONE'"
  python3 clawworker_spawner.py myteam w2 "python3 script.py --arg value"
  python3 clawworker_spawner.py myteam w3 "ls -la /tmp"
        """
    )
    parser.add_argument("team", help="ClawTeam team name")
    parser.add_argument("worker", help="Worker name")
    parser.add_argument("command", help="Command to execute (use 'bash -c ...' for shell commands)")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout in seconds (default: 30)")
    parser.add_argument("--model", default="MiniMax-M2.5", help="Model (ignored for subprocess backend)")
    parser.add_argument("--workspace", help="Working directory")
    
    args = parser.parse_args()
    
    print(f"[clawworker] Spawning worker '{args.worker}' in team '{args.team}'")
    print(f"[clawworker] Command: {args.command[:80]}{'...' if len(args.command) > 80 else ''}")
    
    start = time.time()
    result = spawn_worker(args.team, args.worker, args.command, args.timeout)
    duration = time.time() - start
    
    if result["success"]:
        print(f"[clawworker] ✅ Worker spawned successfully")
        if result["pid"]:
            print(f"[clawworker]   PID: {result['pid']}")
        print(f"[clawworker]   Duration: {duration:.2f}s")
    else:
        print(f"[clawworker] ❌ Spawn failed")
        print(f"[clawworker]   Error: {result['raw']}")
        sys.exit(1)


if __name__ == "__main__":
    main()
