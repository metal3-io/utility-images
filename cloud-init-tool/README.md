# Cloud-init tool

This tool is used to fetch cloud-init status and logs from BaremetalHost. It
accesses the host over SSH.

## Using cloud-init tool

The tool requires two things:

- `TARGET_HOSTS` env variable containing node IP addresses
- SSH key as bind mount

In addition, the user can affect the behavior with following variables:

- `EXTRA_COMMANDS` to run extra commands on BMH
- `PRINT_TO_STDOUT` to print results to container stdout as well
  Mount the log directory to host machine to access the logs
- `SSH_TIMEOUT` to set ssh connection timeout in seconds (default: 10)

The `TARGET_HOSTS` must give the target hosts in format `user@ip-address`.
Multiple hosts can be defined by separating the hosts with `;`. Extra commands
are given in env variable `EXTRA_COMMANDS` and they are separated by `;`. The
output of extra commands are also written to log files under the log directory.
The output of all commands can also be written to container stdout, this can be
enabled with the `PRINT_TO_STDOUT` env variable. The container will write logs
to `/output-logs` directory on the container.

Example command for usage:

``` sh
docker run \
    --net=host \
    -e TARGET_HOSTS="metal3@192.168.111.100" \
    -e EXTRA_COMMANDS="cat /etc/os-release; ls -l /etc" \
    -v "${HOME}/.ssh":/root/.ssh \
    -v ./output-logs:/output-logs \
    cloud-init-tool
```

Notice that `--net=host` is most likely wanted to avoid connection issues.

## Container exit status

The tool returns exit code 0 if all the given hosts have bootstrapped
successfully. If the tool cannot execute properly, for example due to connection
issue, or any of the hosts have not bootstrapped successfully, the tool returns
exit code 1.

The same exit status will also be the exit status of `docker run` command. So
the bootstrapping status can be simply checked by checking the exit code of
`docker run` command.
