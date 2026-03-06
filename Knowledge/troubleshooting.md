# F5 BIG-IP Troubleshooting Guide

## Quick Diagnostics Checklist

```bash
# 1. System health
tmsh show sys version
tmsh show sys failover
tmsh show cm sync-status

# 2. Virtual server status
tmsh show ltm virtual

# 3. Pool member status
tmsh show ltm pool members

# 4. Connection state
tmsh show sys connection count

# 5. System resources
tmsh show sys performance

# 6. Recent errors
tail -100 /var/log/ltm | grep -i error
```

## Common Issues and Solutions

### Virtual Server Shows "Available" but No Traffic

**Diagnosis:**
```bash
# Check VS destination and state
tmsh list ltm virtual /Common/my_vs destination enabled

# Check if port is listening
netstat -an | grep <vip>:<port>

# Verify VIP is on correct interface
tmsh list net self
ip addr show
```

**Common Causes:**
1. Wrong destination IP/port
2. Missing self IP on VLAN
3. Routing issue (no route to client network)
4. Firewall blocking traffic

### Pool Members Marked Down

**Diagnosis:**
```bash
# Check pool member status
tmsh show ltm pool /Common/my_pool members

# Check monitor status
tmsh show ltm pool /Common/my_pool all-properties | grep -A10 monitor

# Test monitor manually
curl -v http://pool_member_ip:port/health

# Check from BIG-IP
tmsh run util bash -c "curl -v http://pool_member_ip:port/health"
```

**Solutions:**
```bash
# Verify monitor send/receive strings
tmsh list ltm monitor http /Common/my_monitor send recv

# Increase timeout
tmsh modify ltm monitor http /Common/my_monitor timeout 31 interval 10

# Check if member can reach monitor source
# BIG-IP uses self IP from same VLAN as pool member
```

### "No Route to Host" Errors

**Diagnosis:**
```bash
# Check routing table
tmsh show net route

# Check self IPs
tmsh list net self

# Verify VLAN configuration
tmsh list net vlan

# Check ARP
tmsh show net arp
```

**Solutions:**
```bash
# Add missing self IP
tmsh create net self /Common/internal_self \
    address 10.0.1.1/24 \
    vlan /Common/internal \
    allow-service default

# Add route if needed
tmsh create net route /Common/backend_route \
    network 192.168.0.0/16 \
    gw 10.0.1.254
```

### Connection Resets (RST)

**Diagnosis:**
```bash
# Enable RST cause logging
tmsh modify sys db connection.rstcause.log value enable
tmsh modify sys db log.tcprst.enabled value true

# Check logs
tail -f /var/log/ltm | grep RST

# Capture traffic
tcpdump -ni 0.0 host <client_ip> and port <port> -w /var/tmp/rst.pcap
```

**Common RST Causes:**
| Error Code | Meaning | Solution |
|------------|---------|----------|
| No route to host | Missing self IP or route | Add self IP on pool VLAN |
| Connection refused | Pool member rejecting | Check backend service |
| Idle timeout | Connection idle too long | Increase idle timeout |
| SNAT port exhaustion | Too many connections per SNAT | Add more SNAT IPs |

### SSL Handshake Failures

**Diagnosis:**
```bash
# Enable SSL debug logging
tmsh modify sys db log.ssl.level value debug

# Check logs
tail -f /var/log/ltm | grep -i ssl

# Test from client
openssl s_client -connect bigip_vip:443 -showcerts

# Check certificate chain
openssl verify -CAfile chain.crt cert.crt
```

**Common Issues:**
```bash
# Certificate key mismatch - compare modulus
openssl x509 -noout -modulus -in cert.crt | md5sum
openssl rsa -noout -modulus -in key.key | md5sum

# Expired certificate
tmsh run sys crypto check-cert certificate /Common/my_cert

# Cipher mismatch
openssl s_client -connect bigip_vip:443 -cipher 'ECDHE-RSA-AES256-GCM-SHA384'
```

### High CPU Usage

**Diagnosis:**
```bash
# Check overall CPU
tmsh show sys performance all-stats

# Check TMM CPU
tmsh show sys tmm-info

# Check per-process CPU
top -bn1 | head -20

# Check iRule statistics
tmsh show ltm rule
```

**Solutions:**
```bash
# Optimize iRules
# - Reduce log statements
# - Use switch instead of multiple if/elseif
# - Cache regex matches

# Check for attack traffic
tmsh show sys connection all-properties | head -50

# Offload SSL to hardware (if available)
tmsh show sys crypto
```

### Memory Issues

**Diagnosis:**
```bash
# Check memory usage
tmsh show sys memory

# Check TMM memory
tmsh show sys tmm-info

# Check connection table size
tmsh show sys connection count

# Check persistence records
tmsh show ltm persistence persist-records count
```

**Solutions:**
```bash
# Clear persistence records
tmsh delete ltm persistence persist-records

# Reduce connection timeouts
tmsh modify ltm profile tcp /Common/tcp idle-timeout 180

# Increase memory allocation (requires reboot)
tmsh modify sys provision ltm level nominal
```

## tcpdump Usage

### Basic Captures
```bash
# Capture on specific interface
tcpdump -ni 1.1 -s0 -w /var/tmp/capture.pcap

# Capture on all interfaces
tcpdump -ni 0.0 -s0 -w /var/tmp/capture.pcap

# Filter by host
tcpdump -ni 0.0 host 192.168.1.100 -w /var/tmp/capture.pcap

# Filter by port
tcpdump -ni 0.0 port 443 -w /var/tmp/capture.pcap

# Filter by host and port
tcpdump -ni 0.0 host 192.168.1.100 and port 443 -w /var/tmp/capture.pcap
```

### F5-Specific Filters
```bash
# Client-side only (external VLAN)
tcpdump -ni external -s0 -w /var/tmp/client.pcap

# Server-side only (internal VLAN)
tcpdump -ni internal -s0 -w /var/tmp/server.pcap

# Both sides for specific client
tcpdump -ni 0.0 '(host 10.0.0.100 or host 192.168.1.50)' -w /var/tmp/both.pcap
```

### Capture with Decryption
```bash
# Export SSL session keys (for Wireshark)
ssldump -Aed -nr /var/tmp/capture.pcap -k /config/ssl/ssl.key/default.key
```

## Log Analysis

### Key Log Files
| Log File | Purpose |
|----------|---------|
| /var/log/ltm | LTM events, errors |
| /var/log/audit | Configuration changes |
| /var/log/ts/bd.log | ASM/AWAF events |
| /var/log/apm | APM authentication |
| /var/log/tmm | TMM process logs |

### Log Search Commands
```bash
# Recent LTM errors
grep -i error /var/log/ltm | tail -50

# Monitor failures
grep -i "monitor.*down\|failed" /var/log/ltm

# Connection issues
grep -i "rst\|timeout\|refused" /var/log/ltm

# Failover events
grep -i failover /var/log/ltm

# Configuration changes
grep -i "created\|modified\|deleted" /var/log/audit
```

### iRule Debugging
```tcl
# Add logging to iRule
when HTTP_REQUEST {
    log local0. "Client: [IP::client_addr], Host: [HTTP::host], URI: [HTTP::uri]"
}
```

```bash
# Watch iRule logs
tail -f /var/log/ltm | grep -i "Rule"
```

## Performance Analysis

### Connection Statistics
```bash
# Connection count by state
tmsh show sys connection count

# Top connections by client
tmsh show sys connection cs-client-addr | sort | uniq -c | sort -rn | head

# Connection rate
tmsh show ltm profile tcp stats
```

### Virtual Server Statistics
```bash
tmsh show ltm virtual /Common/my_vs stats

# Key metrics:
# - Bits In/Out
# - Packets In/Out
# - Current connections
# - Maximum connections
```

### Pool Statistics
```bash
tmsh show ltm pool /Common/my_pool stats

# Per-member statistics
tmsh show ltm pool /Common/my_pool members stats
```

## Quick Fixes

### Restart Services
```bash
# Restart LTM (affects traffic!)
tmsh restart sys service tmm

# Restart management plane only
tmsh restart sys service mcpd

# Restart all services (nuclear option)
tmsh restart sys service all
```

### Clear Connection Table
```bash
# Clear specific connections
tmsh delete sys connection cs-client-addr 192.168.1.100

# Clear all connections (DANGEROUS in production)
tmsh delete sys connection all
```

### Reset Statistics
```bash
tmsh reset-stats ltm virtual /Common/my_vs
tmsh reset-stats ltm pool /Common/my_pool
```

## Qkview and iHealth

### Generate Qkview
```bash
qkview -f /var/tmp/$(hostname)_$(date +%Y%m%d).qkview
```

### Upload to iHealth
```bash
# Via GUI: iHealth website upload
# Via API: 
curl -X POST https://ihealth-api.f5.com/qkview-analyzer/api/qkview \
    -F "qkview=@/var/tmp/qkview.qkview" \
    -H "Authorization: Basic <base64_creds>"
```

## REST API Diagnostics

```bash
# Get system status
curl -sk -u admin:password \
    https://bigip/mgmt/tm/sys/performance

# Get connection count
curl -sk -u admin:password \
    https://bigip/mgmt/tm/sys/connection/count

# Run bash command
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/tm/util/bash \
    -H "Content-Type: application/json" \
    -d '{"command":"run","utilCmdArgs":"-c \"cat /var/log/ltm | tail -100\""}'
```
