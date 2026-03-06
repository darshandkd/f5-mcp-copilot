# F5 BIG-IP High Availability Configuration

## HA Architecture Overview

### Active-Standby
- One device processes traffic (Active)
- One device monitors health (Standby)
- Automatic failover on Active failure
- Most common deployment

### Active-Active
- Both devices process traffic
- Traffic distribution via DNS or network design
- Separate traffic groups for each device
- More complex configuration

## Prerequisites

1. **Network connectivity** between devices (HA VLAN recommended)
2. **Same BIG-IP version** on both units
3. **Same module provisioning**
4. **ConfigSync IP** on each device
5. **Failover unicast/multicast** addresses configured

## Device Trust and Device Group Setup

### Step 1: Configure ConfigSync and Failover IPs

**On Device 1 (bigip1.example.com):**
```bash
# Set ConfigSync address
tmsh modify cm device bigip1.example.com \
    configsync-ip 10.0.99.1

# Set Failover unicast address
tmsh modify cm device bigip1.example.com \
    unicast-address { { ip 10.0.99.1 } { ip management-ip } }

# Set mirroring address (optional)
tmsh modify cm device bigip1.example.com \
    mirror-ip 10.0.99.1 \
    mirror-secondary-ip 10.0.99.1
```

**On Device 2 (bigip2.example.com):**
```bash
tmsh modify cm device bigip2.example.com \
    configsync-ip 10.0.99.2

tmsh modify cm device bigip2.example.com \
    unicast-address { { ip 10.0.99.2 } { ip management-ip } }

tmsh modify cm device bigip2.example.com \
    mirror-ip 10.0.99.2 \
    mirror-secondary-ip 10.0.99.2
```

### Step 2: Establish Device Trust

**On Device 1 (initiating device):**
```bash
tmsh modify cm trust-domain /Common/Root \
    ca-devices add { 10.0.99.2 } \
    name bigip2.example.com \
    username admin \
    password <password>
```

### Step 3: Create Device Group

**On Either Device:**
```bash
tmsh create cm device-group my_device_group \
    type sync-failover \
    devices add { bigip1.example.com bigip2.example.com } \
    auto-sync enabled \
    network-failover enabled
```

### Step 4: Initial Sync

```bash
# Sync from device with desired configuration
tmsh run cm config-sync to-group my_device_group
```

## Traffic Groups

### View Traffic Groups
```bash
tmsh list cm traffic-group
tmsh show cm traffic-group
```

### Create Traffic Group
```bash
tmsh create cm traffic-group /Common/traffic-group-2

# Assign to device
tmsh modify cm traffic-group /Common/traffic-group-2 \
    ha-group /Common/my_ha_group

# Set preferred device
tmsh modify cm traffic-group /Common/traffic-group-2 \
    default-device bigip2.example.com
```

### Assign Objects to Traffic Group
```bash
# Floating Self IP
tmsh create net self /Common/external_float \
    address 10.0.1.100/24 \
    vlan /Common/external \
    traffic-group /Common/traffic-group-1 \
    allow-service default

# Virtual Server
tmsh modify ltm virtual /Common/web_vs \
    traffic-group /Common/traffic-group-1
```

## HA Groups

### Create HA Group
```bash
tmsh create cm ha-group /Common/my_ha_group \
    pools add { /Common/critical_pool { weight 50 } } \
    trunks add { /Common/external_trunk { weight 30 } } \
    active-bonus 10
```

### Configure HA Group Thresholds
```bash
tmsh modify cm ha-group /Common/my_ha_group \
    pools modify { /Common/critical_pool { 
        threshold 2 
        weight 50 
    }}
```

### Assign HA Group to Traffic Group
```bash
tmsh modify cm traffic-group /Common/traffic-group-1 \
    ha-group /Common/my_ha_group \
    auto-failback-enabled true \
    auto-failback-time 60
```

## Failover Configuration

### Manual Failover
```bash
# Go standby
tmsh run sys failover standby

# Go standby for specific traffic group
tmsh run sys failover standby traffic-group /Common/traffic-group-1
```

### Failback Configuration
```bash
# Enable auto-failback
tmsh modify cm traffic-group /Common/traffic-group-1 \
    auto-failback-enabled true \
    auto-failback-time 60
```

### Force Offline
```bash
tmsh run sys failover offline
```

## Connection Mirroring

### Enable Mirroring on Virtual Server
```bash
tmsh modify ltm virtual /Common/web_vs \
    connection-mirroring enabled
```

### Enable Persistence Mirroring
```bash
tmsh modify ltm persistence source-addr /Common/src_persist \
    mirror enabled
```

## Sync Status Commands

```bash
# Show sync status
tmsh show cm sync-status

# Show device status
tmsh show cm device

# Show device group status
tmsh show cm device-group

# Show traffic group status
tmsh show cm traffic-group

# Show failover status
tmsh show sys failover
```

## Sync Operations

### Sync to Group
```bash
tmsh run cm config-sync to-group my_device_group
```

### Force Full Load Push
```bash
tmsh run cm config-sync force-full-load-push to-group my_device_group
```

### Sync from Peer
```bash
tmsh run cm config-sync from-device bigip2.example.com
```

## Troubleshooting HA

### Check HA Status
```bash
# Quick status check
tmsh show cm sync-status | grep -E "Mode|Color|Status"

# Detailed status
tmsh show cm device-group
```

### Common Sync Issues

**"Changes Pending" state:**
```bash
# Check what's out of sync
tmsh show cm sync-status

# Force sync
tmsh run cm config-sync to-group my_device_group
```

**"Disconnected" state:**
```bash
# Check network connectivity
ping 10.0.99.2  # ConfigSync IP

# Check iQuery process
tmctl -a iquery

# Restart mcpd
tmsh restart sys service mcpd
```

**Certificate mismatch:**
```bash
# Re-establish trust (on initiating device)
tmsh modify cm trust-domain /Common/Root \
    ca-devices add { <peer-ip> } \
    name <peer-hostname> \
    username admin \
    password <password>
```

### HA Failover Logs
```bash
tail -f /var/log/ltm | grep -i failover
tail -f /var/log/audit
```

## REST API for HA

### Get Failover Status
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/cm/failover-status
```

### Get Sync Status
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/cm/sync-status
```

### Trigger Sync
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/cm \
    -H "Content-Type: application/json" \
    -d '{"command":"run","utilCmdArgs":"config-sync to-group my_device_group"}'
```

### Force Standby
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/sys \
    -H "Content-Type: application/json" \
    -d '{"command":"run","utilCmdArgs":"failover standby"}'
```

## Active-Active Configuration

### Create Second Traffic Group
```bash
tmsh create cm traffic-group /Common/traffic-group-2

tmsh modify cm traffic-group /Common/traffic-group-2 \
    default-device bigip2.example.com
```

### Assign Resources to Traffic Groups

**Traffic Group 1 (Active on bigip1):**
```bash
tmsh modify net self /Common/float_app1 \
    traffic-group /Common/traffic-group-1

tmsh modify ltm virtual /Common/app1_vs \
    traffic-group /Common/traffic-group-1
```

**Traffic Group 2 (Active on bigip2):**
```bash
tmsh modify net self /Common/float_app2 \
    traffic-group /Common/traffic-group-2

tmsh modify ltm virtual /Common/app2_vs \
    traffic-group /Common/traffic-group-2
```

## MAC Masquerade

### Configure MAC Masquerade
```bash
# For each traffic group
tmsh modify cm traffic-group /Common/traffic-group-1 \
    mac f5:f5:f5:f5:f5:01

tmsh modify cm traffic-group /Common/traffic-group-2 \
    mac f5:f5:f5:f5:f5:02
```

## vCMP Guest HA Considerations

```bash
# On vCMP guest, ensure guest cluster is synced
tmsh show vcmp guest

# Traffic groups in guest operate independently from host
```
