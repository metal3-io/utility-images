# Metal3 Keepalived

Keepalived container used in Ironic deployments. Keepalived provides a fixed
IP address for Ironic in such a manner that even after pivoting operations the
IP of Ironic stays persistent.

See the [Keepalived documentation](https://www.keepalived.org/manpage.html)
for the meaning of the underlying directives.

## Environment variables

| Variable | Default | Description |
|----------|---------|-------------|
| `CUSTOM_CONF_DIR` | `/conf` | A subdirectory named `keepalived` is created under this path, the config file is copied there and the variable substitution happens in that copy |
| `CUSTOM_DATA_DIR` | `/data` | A subdirectory named `keepalived` is created here to hold the keepalived and vrrp pid files |
| `PROVISIONING_IP` | - | The fixed IP provided by keepalived (legacy mode, see below) |
| `PROVISIONING_INTERFACE` | - | The name of the interface that will be used to "host" the fixed IP (legacy mode, see below) |
| `KEEPALIVED_VIRTUAL_IPS` | - | Space-separated list of virtual IPs with their interfaces, each entry has the format `ip,interface[,prefix]`. When set, it takes precedence over `PROVISIONING_IP` and `PROVISIONING_INTERFACE` |
| `KEEPALIVED_VRID` | `1` | VRRP virtual router ID, an integer in the range 1..255 |
| `KEEPALIVED_AUTH_PASS` | - | VRRP simple authentication password, given inline. When unset and `KEEPALIVED_AUTH_PASS_FILE` is also unset, no `authentication` block is generated |
| `KEEPALIVED_AUTH_PASS_FILE` | - | Path to a file holding the VRRP authentication password, typically a mounted Secret. Mutually exclusive with `KEEPALIVED_AUTH_PASS` |

## Configuration modes

**Legacy mode** (single IP): Use `PROVISIONING_IP` and `PROVISIONING_INTERFACE`
for simple single-IP deployments. The script automatically detects IPv4 vs IPv6
and applies the correct prefix (`/32` for IPv4, `/128` for IPv6).

```bash
PROVISIONING_IP=192.168.0.100
PROVISIONING_INTERFACE=eth0
```

**Multi-IP mode**: Use `KEEPALIVED_VIRTUAL_IPS` for multiple IPs, different
interfaces, or mixed IPv4/IPv6 deployments. Format is space-separated entries
where each entry is `ip,interface[,prefix]`.

```bash
# Two IPs on different interfaces
KEEPALIVED_VIRTUAL_IPS="192.168.0.100,eth0 192.168.1.50,eth1"

# IPv6 with link-local address
KEEPALIVED_VIRTUAL_IPS="fe80::1,eth0,64 fd00::100,eth0,128"

# Mixed IPv4 and IPv6
KEEPALIVED_VIRTUAL_IPS="192.168.0.100,eth0 fd00::100,eth0"
```

## Virtual router ID

`KEEPALIVED_VRID` sets the `virtual_router_id` of the VRRP instance and
defaults to `1`. It must be identical on every peer that takes part in the same
VRRP group, and it must be unique among the VRRP groups that share a broadcast
domain, otherwise unrelated instances will fight over the same virtual IP.

```bash
KEEPALIVED_VRID=51
```

## VRRP authentication

Setting a password enables VRRP simple authentication, which adds the
following block to the generated configuration:

```text
authentication {
    auth_type PASS
    auth_pass <password>
}
```

The recommended way to pass the password is `KEEPALIVED_AUTH_PASS_FILE`
pointing at a mounted Secret, so that the plaintext never appears in the pod
spec:

```bash
KEEPALIVED_AUTH_PASS_FILE=/etc/keepalived-auth/password
```

The password may also be given inline for local testing:

```bash
KEEPALIVED_AUTH_PASS=m3talpwd
```

Setting both variables at once is an error and the container exits.

The password must not contain whitespace, double quotes, backslashes, `~` or
non-printable characters. Leading and trailing whitespace is trimmed from the
file form, so a trailing newline in a Secret is harmless.

VRRP truncates `auth_pass` to 8 bytes, so only the first 8 characters take
part in the comparison between peers. A longer password is accepted but logs a
warning.

The password never appears in the container logs. It is only written to the
generated `keepalived.conf` inside the container.

## Matching the settings across peers

`KEEPALIVED_VRID` and the authentication password must match on all peers of
the same VRRP group. When they do not match, the peers cannot recognise each
other's advertisements, every node promotes itself to MASTER, and the virtual
IP ends up assigned on more than one host at the same time (split brain /
duplicate VIP).

## Notes

If run with a container that has a read-only root file-system, then
`CUSTOM_CONF_DIR`, `CUSTOM_DATA_DIR` and `/var/log` paths have to be mounted
from an external volume.
