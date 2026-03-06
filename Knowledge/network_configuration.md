# F5 BIG-IP Network Configuration Guide

## Network Architecture

### Self IP Types
| Type | Purpose |
|------|---------|
| Non-floating | Unique to each device, used for management/HA |
| Floating | Shared between HA pair, moves with traffic group |

### Port Lockdown
| Setting | Services Allowed |
|---------|------------------|
| Allow None | No services |
| Allow Default | Essential F5 services (SSH, web, SNMP, etc.) |
| Allow All | All services |
| Allow Custom | User-specified services |

## VLAN Configuration

### Create Untagged VLAN
```bash
tmsh create net vlan external \
    interfaces add { 1.1 { untagged } }
```

### Create Tagged VLAN
```bash
tmsh create net vlan external_100 \
    tag 100 \
    interfaces add { 1.1 { tagged } }
```

### Create VLAN with Multiple Interfaces
```bash
tmsh create net vlan internal \
    interfaces add { 
        1.2 { untagged } 
        1.3 { untagged } 
    }
```

### VLAN Failsafe
```bash
tmsh modify net vlan external \
    failsafe enabled \
    failsafe-timeout 90 \
    failsafe-action failover
```

## Self IP Configuration

### Create Non-Floating Self IP
```bash
tmsh create net self external_self \
    address 10.0.1.10/24 \
    vlan external \
    allow-service default
```

### Create Floating Self IP
```bash
tmsh create net self external_float \
    address 10.0.1.100/24 \
    vlan external \
    traffic-group traffic-group-1 \
    allow-service default
```

### Port Lockdown Examples
```bash
# Allow all
tmsh create net self my_self \
    address 10.0.1.10/24 \
    vlan internal \
    allow-service all

# Allow none
tmsh create net self secure_self \
    address 10.0.1.11/24 \
    vlan dmz \
    allow-service none

# Allow custom
tmsh create net self custom_self \
    address 10.0.1.12/24 \
    vlan internal \
    allow-service add { tcp:443 tcp:80 }
```

## Routing

### Default Route
```bash
tmsh create net route default_gw \
    network default \
    gw 10.0.1.1
```

### Static Route
```bash
tmsh create net route backend_route \
    network 192.168.0.0/16 \
    gw 10.0.2.1
```

### Route with Specific VLAN
```bash
tmsh create net route internal_route \
    network 172.16.0.0/12 \
    gw 10.0.2.254 \
    vlan internal
```

### Route Domain Routes
```bash
tmsh create net route /RD10/backend_route \
    network 10.0.0.0/8 \
    gw 192.168.1.1
```

### View Routing Table
```bash
tmsh show net route
tmsh list net route

# Kernel routing table
ip route show
netstat -rn
```

## SNAT Configuration

### When SNAT is Required
- Server default gateway is NOT the BIG-IP
- One-arm deployment
- Client and server on same subnet
- Asymmetric routing scenarios

### Auto Map
```bash
tmsh modify ltm virtual /Common/my_vs \
    source-address-translation { type automap }
```

### SNAT Pool
```bash
# Create SNAT pool
tmsh create ltm snatpool /Common/web_snatpool \
    members add { 
        10.0.1.200 
        10.0.1.201 
        10.0.1.202 
    }

# Apply to virtual server
tmsh modify ltm virtual /Common/my_vs \
    source-address-translation { 
        type snat 
        pool /Common/web_snatpool 
    }
```

### Standalone SNAT
```bash
tmsh create ltm snat /Common/outbound_snat \
    origins add { 192.168.0.0/24 } \
    translation /Common/10.0.1.200 \
    vlans-enabled \
    vlans add { internal }
```

## Trunks (Link Aggregation)

### Create Trunk
```bash
tmsh create net trunk external_trunk \
    interfaces add { 1.1 1.2 } \
    lacp enabled
```

### Trunk with LACP
```bash
tmsh create net trunk ha_trunk \
    interfaces add { 1.3 1.4 } \
    lacp enabled \
    lacp-mode active \
    lacp-timeout short
```

### Add VLAN to Trunk
```bash
tmsh create net vlan external \
    interfaces add { external_trunk { untagged } }
```

## Route Domains

### Create Route Domain
```bash
tmsh create net route-domain RD10 \
    id 10 \
    vlans add { tenant1_vlan }
```

### Create Objects in Route Domain
```bash
# Self IP in route domain
tmsh create net self /RD10/tenant1_self \
    address 10.0.1.1%10/24 \
    vlan /Common/tenant1_vlan

# Virtual server in route domain
tmsh create ltm virtual /RD10/tenant1_vs \
    destination 10.0.1.100%10:80 \
    pool /RD10/tenant1_pool
```

### Route Domain Parent
```bash
tmsh modify net route-domain RD10 \
    parent /Common/0
```

## Interface Configuration

### View Interfaces
```bash
tmsh show net interface
tmsh list net interface
```

### Enable/Disable Interface
```bash
tmsh modify net interface 1.1 disabled
tmsh modify net interface 1.1 enabled
```

### Set Media Type
```bash
tmsh modify net interface 1.1 media-fixed 10000T-FD
```

### Interface Statistics
```bash
tmsh show net interface 1.1 field-fmt
```

## DNS Configuration

### Configure DNS Servers
```bash
tmsh modify sys dns name-servers add { 8.8.8.8 8.8.4.4 }
```

### Configure DNS Search Domain
```bash
tmsh modify sys dns search add { example.com corp.example.com }
```

### DNS Resolver (for BIG-IP processes)
```bash
tmsh create net dns-resolver /Common/f5_dns_resolver \
    answer-default-zones yes \
    cache-size 5767168 \
    forward-zones add { 
        . { nameservers add { 8.8.8.8:53 8.8.4.4:53 } }
    }
```

## NTP Configuration

```bash
tmsh modify sys ntp servers add { 
    0.pool.ntp.org 
    1.pool.ntp.org 
}
tmsh modify sys ntp timezone America/Los_Angeles
```

## ARP and MAC

### View ARP Table
```bash
tmsh show net arp
```

### Static ARP Entry
```bash
tmsh create net arp static_arp \
    ip-address 10.0.1.50 \
    mac-address 00:11:22:33:44:55
```

### Clear ARP Cache
```bash
tmsh delete net arp all
```

### MAC Masquerade (for HA)
```bash
tmsh modify cm traffic-group /Common/traffic-group-1 \
    mac f5:f5:f5:f5:f5:01
```

## Packet Filters

### Create Packet Filter Rule
```bash
tmsh create net packet-filter-rule block_ssh \
    action reject \
    ip-protocol tcp \
    destination-port-list add { ssh }
```

### Apply Packet Filter
```bash
tmsh modify net packet-filter \
    rules add { block_ssh }
```

## VLAN Groups (Spanning Tree)

```bash
tmsh create net vlan-group my_vlan_group \
    bridge-traffic enabled \
    members add { vlan1 vlan2 }
```

## Management Interface

### Configure Management IP
```bash
tmsh modify sys global-settings mgmt-dhcp disabled
tmsh create sys management-ip 192.168.1.245/24

# Management route
tmsh create sys management-route default gateway 192.168.1.1
```

### Allow Management Services
```bash
tmsh modify sys httpd allow add { 192.168.1.0/24 }
tmsh modify sys sshd allow add { 192.168.1.0/24 }
```

## Network Troubleshooting

### Connectivity Tests
```bash
# Ping from TMM (through data plane)
tmsh run util ping -c 3 10.0.1.1

# Ping from management
ping 192.168.1.1

# Traceroute
traceroute 10.0.1.100
```

### Check Self IP Routing
```bash
# Verify self IP exists
tmsh list net self

# Check which self IP is used for pool members
tmsh show ltm pool /Common/my_pool field-fmt | grep "self"
```

### Verify VLAN Connectivity
```bash
# Check VLAN status
tmsh show net vlan

# Check interface in VLAN
tmsh show net interface 1.1

# tcpdump on VLAN
tcpdump -ni external host 10.0.1.100
```

### Route Verification
```bash
# Show effective routes
ip route show

# Show routes for specific destination
ip route get 192.168.1.100
```

## Common Network Issues

### No Route to Host
1. Check self IP exists on correct VLAN
2. Check route exists for destination network
3. Verify gateway is reachable
4. Check ARP resolution

### Asymmetric Routing
1. Add SNAT to virtual server
2. Or ensure return traffic goes through BIG-IP
3. Configure server default gateway to BIG-IP

### VLAN Not Forwarding
1. Check interface is up
2. Verify VLAN tagging matches switch
3. Check spanning tree state
4. Verify trunk configuration
