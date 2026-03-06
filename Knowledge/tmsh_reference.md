# F5 TMSH Command Reference

## Command Structure

```
tmsh <verb> <module> <component> [name] [options]
```

**Verbs:** list, show, create, modify, delete, save, load, run

## System Commands

### Version and Status
```bash
tmsh show sys version
tmsh show sys hardware
tmsh show sys software
tmsh show sys license
tmsh show sys provision
tmsh show sys performance
```

### Configuration Management
```bash
# Save running config
tmsh save sys config

# Save to specific file
tmsh save sys config file my_backup.scf

# Load configuration
tmsh load sys config file my_backup.scf

# Merge configuration
tmsh load sys config merge file partial_config.scf

# Reset to default
tmsh load sys config default
```

### High Availability
```bash
tmsh show sys failover
tmsh show cm sync-status
tmsh show cm device
tmsh show cm device-group

# Force standby
tmsh run sys failover standby

# Sync configuration
tmsh run cm config-sync to-group <group-name>

# Force full sync
tmsh run cm config-sync force-full-load-push to-group <group-name>
```

## Network Commands

### Self IPs
```bash
# List all self IPs
tmsh list net self

# Create self IP
tmsh create net self internal_self \
    address 10.0.1.1/24 \
    vlan internal \
    allow-service default

# Show self IP details
tmsh show net self internal_self
```

### VLANs
```bash
# List VLANs
tmsh list net vlan

# Create VLAN
tmsh create net vlan internal \
    interfaces add { 1.1 { untagged } }

# Create tagged VLAN
tmsh create net vlan external_100 \
    tag 100 \
    interfaces add { 1.2 { tagged } }
```

### Routes
```bash
# List routes
tmsh list net route

# Show route table
tmsh show net route

# Create static route
tmsh create net route default_gw \
    network default \
    gw 10.0.0.1

# Create route with VLAN
tmsh create net route internal_route \
    network 192.168.0.0/16 \
    gw 10.0.1.254 \
    vlan internal
```

### ARP
```bash
tmsh show net arp
tmsh delete net arp all
```

### Interfaces
```bash
tmsh show net interface
tmsh show net interface 1.1
tmsh modify net interface 1.1 media-fixed 10000T-FD
```

## LTM Commands

### Virtual Servers
```bash
# List virtual servers
tmsh list ltm virtual

# Show status
tmsh show ltm virtual

# Show specific VS
tmsh show ltm virtual /Common/my_vs

# Create virtual server
tmsh create ltm virtual /Common/web_vs \
    destination 10.0.0.100:443 \
    ip-protocol tcp \
    pool /Common/web_pool \
    profiles add { /Common/tcp /Common/http }

# Modify virtual server
tmsh modify ltm virtual /Common/web_vs \
    pool /Common/new_pool

# Delete virtual server
tmsh delete ltm virtual /Common/web_vs

# Enable/disable
tmsh modify ltm virtual /Common/web_vs disabled
tmsh modify ltm virtual /Common/web_vs enabled
```

### Pools
```bash
# List pools
tmsh list ltm pool

# Show pool status
tmsh show ltm pool
tmsh show ltm pool /Common/web_pool

# Show pool members
tmsh show ltm pool /Common/web_pool members

# Create pool
tmsh create ltm pool /Common/web_pool \
    members add { 
        10.0.0.10:80 
        10.0.0.11:80 
    } \
    monitor /Common/http

# Add pool member
tmsh modify ltm pool /Common/web_pool \
    members add { 10.0.0.12:80 }

# Remove pool member
tmsh modify ltm pool /Common/web_pool \
    members delete { 10.0.0.12:80 }

# Disable pool member
tmsh modify ltm pool /Common/web_pool \
    members modify { 10.0.0.10:80 { state user-disabled } }

# Force offline (no new/existing connections)
tmsh modify ltm pool /Common/web_pool \
    members modify { 10.0.0.10:80 { state user-down } }
```

### Nodes
```bash
tmsh list ltm node
tmsh show ltm node
tmsh create ltm node /Common/server1 address 10.0.0.10
tmsh modify ltm node /Common/server1 state user-disabled
```

### Monitors
```bash
tmsh list ltm monitor
tmsh list ltm monitor http
tmsh show ltm monitor http /Common/my_monitor

tmsh create ltm monitor http /Common/custom_http \
    defaults-from /Common/http \
    interval 10 \
    timeout 31 \
    send "GET /health HTTP/1.1\r\nHost: example.com\r\n\r\n" \
    recv "OK"
```

### Profiles
```bash
# List profile types
tmsh list ltm profile

# TCP profiles
tmsh list ltm profile tcp
tmsh create ltm profile tcp /Common/custom_tcp \
    defaults-from /Common/tcp \
    idle-timeout 300

# HTTP profiles
tmsh list ltm profile http
tmsh create ltm profile http /Common/custom_http \
    defaults-from /Common/http \
    insert-xforwarded-for enabled

# SSL profiles
tmsh list ltm profile client-ssl
tmsh list ltm profile server-ssl
```

### Persistence
```bash
tmsh list ltm persistence
tmsh show ltm persistence persist-records
tmsh delete ltm persistence persist-records
```

### iRules
```bash
tmsh list ltm rule
tmsh list ltm rule /Common/my_irule
tmsh show ltm rule /Common/my_irule

# Create iRule (inline)
tmsh create ltm rule /Common/redirect_rule { 
when HTTP_REQUEST {
    HTTP::redirect https://[HTTP::host][HTTP::uri]
}
}

# Apply to virtual server
tmsh modify ltm virtual /Common/web_vs \
    rules add { /Common/redirect_rule }
```

## SSL/TLS Commands

```bash
# List certificates
tmsh list sys crypto cert

# List keys
tmsh list sys crypto key

# Import certificate
tmsh install sys crypto cert my_cert from-local-file /var/tmp/cert.crt

# Import key
tmsh install sys crypto key my_key from-local-file /var/tmp/key.key

# Create client SSL profile
tmsh create ltm profile client-ssl /Common/my_clientssl \
    cert /Common/my_cert.crt \
    key /Common/my_key.key \
    chain /Common/my_chain.crt
```

## Connection Commands

```bash
# Show active connections
tmsh show sys connection

# Filter by client IP
tmsh show sys connection cs-client-addr 192.168.1.100

# Filter by server IP
tmsh show sys connection cs-server-addr 10.0.0.10

# Show connection count
tmsh show sys connection count

# Delete connections
tmsh delete sys connection cs-client-addr 192.168.1.100
```

## Logging and Debugging

```bash
# View logs
tmsh show sys log ltm
tmsh show sys log audit

# Follow logs
tail -f /var/log/ltm
tail -f /var/log/tmm

# iRule debug logging
log local0. "Debug: [IP::client_addr]"
```

## Database Variables

```bash
# List all DB keys
tmsh list sys db

# Show specific key
tmsh list sys db connection.vlankeyed

# Modify DB variable
tmsh modify sys db connection.vlankeyed value enable

# Common DB variables
tmsh modify sys db tmm.ht.split value enable
tmsh modify sys db log.tcprst.enabled value true
tmsh modify sys db connection.rstcause.log value true
```

## UCS Backup

```bash
# Create UCS backup
tmsh save sys ucs /var/local/ucs/backup_$(date +%Y%m%d).ucs

# Load UCS
tmsh load sys ucs /var/local/ucs/backup.ucs

# Load UCS without license
tmsh load sys ucs /var/local/ucs/backup.ucs no-license
```

## Useful Shortcuts

```bash
# Show all virtual servers and their status in one line
tmsh show ltm virtual | grep -E "^Ltm|Availability|State"

# Quick pool member status
tmsh show ltm pool | grep -E "^Ltm|Availability|Active"

# Export single object config
tmsh list ltm virtual /Common/my_vs one-line

# Export in tmsh format (for scripting)
tmsh list ltm virtual /Common/my_vs all-properties
```
