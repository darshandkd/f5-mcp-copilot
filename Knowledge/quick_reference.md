# F5 BIG-IP Quick Reference Cheat Sheet

## Status Commands

```bash
# System overview
tmsh show sys version                    # Version info
tmsh show sys hardware                   # Hardware info
tmsh show sys license                    # License status
tmsh show sys failover                   # HA status
tmsh show cm sync-status                 # Sync status
tmsh show sys performance                # Performance stats

# LTM status
tmsh show ltm virtual                    # All virtual servers
tmsh show ltm pool                       # All pools
tmsh show ltm pool members               # All pool members
tmsh show ltm node                       # All nodes
```

## Virtual Server Quick Commands

```bash
# Create
tmsh create ltm virtual my_vs destination 10.0.0.100:443 pool my_pool profiles add { tcp http }

# Modify
tmsh modify ltm virtual my_vs pool new_pool

# Enable/Disable
tmsh modify ltm virtual my_vs enabled
tmsh modify ltm virtual my_vs disabled

# Delete
tmsh delete ltm virtual my_vs

# List
tmsh list ltm virtual my_vs
```

## Pool Quick Commands

```bash
# Create
tmsh create ltm pool my_pool members add { 10.0.0.10:80 10.0.0.11:80 } monitor http

# Add member
tmsh modify ltm pool my_pool members add { 10.0.0.12:80 }

# Remove member
tmsh modify ltm pool my_pool members delete { 10.0.0.12:80 }

# Disable member (graceful)
tmsh modify ltm pool my_pool members modify { 10.0.0.10:80 { state user-disabled } }

# Force offline
tmsh modify ltm pool my_pool members modify { 10.0.0.10:80 { state user-down } }

# Enable member
tmsh modify ltm pool my_pool members modify { 10.0.0.10:80 { state user-enabled } }
```

## Monitor Quick Commands

```bash
# Create HTTP monitor
tmsh create ltm monitor http custom_http send "GET /health HTTP/1.1\r\n\r\n" recv "200 OK"

# Create TCP monitor
tmsh create ltm monitor tcp custom_tcp interval 5 timeout 16

# Apply to pool
tmsh modify ltm pool my_pool monitor custom_http
```

## Network Quick Commands

```bash
# Create VLAN
tmsh create net vlan internal interfaces add { 1.1 { untagged } }

# Create Self IP
tmsh create net self internal_self address 10.0.1.1/24 vlan internal allow-service default

# Create Route
tmsh create net route default_gw network default gw 10.0.1.254

# Show ARP
tmsh show net arp
```

## Configuration Management

```bash
# Save config
tmsh save sys config

# Load config
tmsh load sys config

# Backup UCS
tmsh save sys ucs /var/local/ucs/backup.ucs

# Restore UCS
tmsh load sys ucs /var/local/ucs/backup.ucs

# Generate qkview
qkview -f /var/tmp/$(hostname)_$(date +%Y%m%d).qkview
```

## HA Commands

```bash
# Go standby
tmsh run sys failover standby

# Force sync
tmsh run cm config-sync to-group my_device_group

# Force full sync
tmsh run cm config-sync force-full-load-push to-group my_device_group
```

## Connection Management

```bash
# Show connections
tmsh show sys connection

# Show connection count
tmsh show sys connection count

# Filter by client
tmsh show sys connection cs-client-addr 192.168.1.100

# Kill connections
tmsh delete sys connection cs-client-addr 192.168.1.100
```

## SSL/TLS Commands

```bash
# Import cert
tmsh install sys crypto cert my_cert from-local-file /var/tmp/cert.crt

# Import key
tmsh install sys crypto key my_key from-local-file /var/tmp/key.key

# Check cert expiry
tmsh run sys crypto check-cert certificate /Common/my_cert

# List certs
tmsh list sys crypto cert
```

## Troubleshooting Commands

```bash
# Follow LTM log
tail -f /var/log/ltm

# Enable RST cause logging
tmsh modify sys db connection.rstcause.log value enable

# tcpdump
tcpdump -ni 0.0 host 10.0.0.100 -w /var/tmp/capture.pcap

# Check persistence
tmsh show ltm persistence persist-records

# Clear persistence
tmsh delete ltm persistence persist-records
```

## REST API Quick Reference

```bash
# Get pools
curl -sk -u admin:pass https://bigip/mgmt/tm/ltm/pool

# Get virtual servers
curl -sk -u admin:pass https://bigip/mgmt/tm/ltm/virtual

# Create pool
curl -sk -u admin:pass -X POST https://bigip/mgmt/tm/ltm/pool \
    -H "Content-Type: application/json" \
    -d '{"name":"my_pool","members":[{"name":"10.0.0.10:80"}]}'

# Disable pool member
curl -sk -u admin:pass -X PATCH \
    https://bigip/mgmt/tm/ltm/pool/~Common~my_pool/members/~Common~10.0.0.10:80 \
    -H "Content-Type: application/json" \
    -d '{"state":"user-disabled"}'

# Save config
curl -sk -u admin:pass -X POST https://bigip/mgmt/tm/sys/config \
    -H "Content-Type: application/json" \
    -d '{"command":"save"}'
```

## Log File Locations

| Log | Path |
|-----|------|
| LTM | /var/log/ltm |
| Audit | /var/log/audit |
| APM | /var/log/apm |
| ASM | /var/log/ts/bd.log |
| TMM | /var/log/tmm |
| System | /var/log/messages |

## Key DB Variables

```bash
# Enable RST logging
tmsh modify sys db connection.rstcause.log value enable

# Enable TCP RST logging  
tmsh modify sys db log.tcprst.enabled value true

# Enable HT-Split
tmsh modify sys db tmm.ht.split value enable

# Show all DB vars
tmsh list sys db
```

## Common Monitor Strings

### HTTP
```
send: GET /health HTTP/1.1\r\nHost: example.com\r\nConnection: close\r\n\r\n
recv: 200 OK
```

### HTTPS
```
send: GET /health HTTP/1.1\r\nHost: example.com\r\n\r\n
recv: healthy
```

### TCP
```
send: (empty or custom string)
recv: (expected response)
```

## Load Balancing Methods

| Short Name | Full Name |
|------------|-----------|
| rr | round-robin |
| ratio | ratio-member |
| lc | least-connections-member |
| fastest | fastest-node |
| observed | observed-member |
| predictive | predictive-member |

## Virtual Server Types

| Type | Use Case |
|------|----------|
| Standard | Full L7 processing |
| Performance (L4) | High throughput L4 |
| Forwarding (IP) | IP routing |
| Forwarding (L2) | L2 bridging |
| Reject | Block traffic |
| DHCP Relay | DHCP forwarding |

## SNAT Types

| Type | Description |
|------|-------------|
| None | No translation |
| Automap | Use self IP from egress VLAN |
| SNAT Pool | Use IP from specified pool |

## Persistence Types

| Type | Use Case |
|------|----------|
| Source Address | Simple IP-based |
| Cookie | HTTP cookie-based |
| SSL | SSL session ID |
| Universal | iRule-controlled |
| Destination Address | Server-side affinity |
