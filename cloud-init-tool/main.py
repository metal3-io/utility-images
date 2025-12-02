import subprocess
import os
import sys
from enum import Enum


# The env variables used to configure the program.
class Vars(Enum):
    HOSTS = "TARGET_HOSTS"
    EXTRA = "EXTRA_COMMANDS"
    PRINT = "PRINT_TO_STDOUT"
    SSH_TIMEOUT = "SSH_TIMEOUT"


DEFAULT_LOGS = {
    "cloud-init-output": "sudo cat /var/log/cloud-init-output.log",
    "cloud-init": "sudo cat /var/log/cloud-init.log",
    "systemctl-status-cloud-init": "systemctl status cloud-init",
    "journalctl-cloud-init": "sudo journalctl -u cloud-init --no-pager",
}

LOG_DIR = "/output-logs"
SUCCESS_COMMAND = "sudo cat /run/cluster-api/bootstrap-success.complete"


# Parses the env variables and saves them in more usable form to dictionary.
def parse_env() -> dict:
    cfg = {}
    for var in Vars:
        cfg[var] = os.environ.get(var.value, "")

    if not cfg[Vars.HOSTS]:
        print(f"ERROR: environment variable {Vars.HOSTS.value} is required")
        sys.exit(1)

    # Normalize values
    cfg[Vars.HOSTS] = [c.strip() for c in cfg[Vars.HOSTS].split(";")]
    cfg[Vars.EXTRA] = [c.strip() for c in cfg[Vars.EXTRA].split(";") if c.strip()]
    if cfg[Vars.PRINT] == "true":
        cfg[Vars.PRINT] = True
    else:
        cfg[Vars.PRINT] = False

    if not cfg[Vars.SSH_TIMEOUT]:
        cfg[Vars.SSH_TIMEOUT] = 10
    else:
        try:
            cfg[Vars.SSH_TIMEOUT] = int(cfg[Vars.SSH_TIMEOUT])
        except ValueError as e:
            print("ERROR: SSH_TIMEOUT variable did not contain a number, exiting.")
            sys.exit(1)

    return cfg


def run_ssh_command(
    ip: str,
    command: str,
    file: str,
    write_to_file: bool,
    write_to_stdout: bool,
    ssh_timeout: int,
) -> bool:
    try:
        # BatchMode: execute commands without being prompted
        # StrictHostKeyChecking: accept server's keys always
        res = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "StrictHostKeyChecking=no",
                ip,
                command,
            ],
            capture_output=True,
            timeout=ssh_timeout,
            text=True,
        )

        if write_to_file:
            with open(file, "w", encoding="utf-8") as f:
                f.write(
                    f"Command '{command}' exited with returncode {res.returncode}.\n"
                )
                f.write(f"stdout: {res.stdout}")
                f.write(f"stderr: {res.stderr}")

        if write_to_stdout:
            print(f"Command '{command}' exited with returncode {res.returncode}.\n")
            print(f"stdout: {res.stdout}")
            print(f"stderr: {res.stderr}")

        if res.returncode != 0:
            return False

        return True
    except Exception as e:
        print(f"ERROR: ssh command terminated with: {e}")
        return False


def main():
    cfg = parse_env()

    # Create log directory
    try:
        os.mkdir(LOG_DIR)
    except FileExistsError:
        print(f"Directory '{LOG_DIR}' already exists.")
    except PermissionError:
        print("ERROR: cannot create working directory, permission denied, aborting.")
        sys.exit(1)

    # Iterate over all hosts
    successful_nodes = 0
    for ip in cfg[Vars.HOSTS]:
        # Check host availability
        success = run_ssh_command(ip, "true", "", False, False, cfg[Vars.SSH_TIMEOUT])
        if not success:
            print(
                f"ERROR: node {ip} not available. ", 
                "Have you mounted SSH keys and operate in correct network?"
            )
            continue

        # Create node directory
        node_dir = f"{LOG_DIR}/{ip}"
        try:
            os.mkdir(node_dir)
        except FileExistsError:
            print(f"Directory '{node_dir}' already exists.")
        except PermissionError:
            print(
                f"ERROR: cannot create node directory, permission denied, skipping node {ip}."
            )
            continue

        # Check the bootstrapping success file
        success = run_ssh_command(
            ip,
            SUCCESS_COMMAND,
            f"{node_dir}/bootstrap-success.log",
            True,
            cfg[Vars.PRINT],
            cfg[Vars.SSH_TIMEOUT],
        )
        if success:
            successful_nodes += 1

        # Collect default logs
        for file, command in DEFAULT_LOGS.items():
            run_ssh_command(
                ip,
                command,
                f"{node_dir}/{file}.log",
                True,
                cfg[Vars.PRINT],
                cfg[Vars.SSH_TIMEOUT],
            )

        # Run extra commands
        extra_command_index = 0
        for command in cfg[Vars.EXTRA]:
            extra_command_index += 1
            run_ssh_command(
                ip,
                command,
                f"{node_dir}/{extra_command_index}.log",
                True,
                cfg[Vars.PRINT],
                cfg[Vars.SSH_TIMEOUT],
            )

    # Produce summary and exit code
    total_nodes = len(cfg[Vars.HOSTS])
    if successful_nodes == total_nodes:
        print("bootstrapping for all nodes has succeeded")
        sys.exit(0)
    else:
        print(f"ERROR: {successful_nodes}/{total_nodes} have succeeded")
        sys.exit(1)


if __name__ == "__main__":
    main()
