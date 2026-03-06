# F5 TCP Express and Performance Optimization

## TCP Express Overview

TCP Express is F5's advanced TCP stack optimization that provides:
- Connection offloading
- TCP optimization
- Bandwidth management
- Latency reduction

## TCP Profile Configuration

### High-Performance Profile
```bash
tmsh create ltm profile tcp /Common/tcp_optimized \
    defaults-from /Common/tcp \
    idle-timeout 300 \
    nagle disabled \
    time-wait-recycle enabled \
    delayed-acks disabled \
    init-cwnd 10 \
    init-rwnd 10 \
    send-buffer-size 131072 \
    receive-window-size 131072
```

### WAN-Optimized Profile
```bash
tmsh create ltm profile tcp /Common/tcp_wan \
    defaults-from /Common/tcp-wan-optimized \
    proxy-buffer-high 131072 \
    proxy-buffer-low 98304 \
    congestion-control woodside
```

### LAN-Optimized Profile
```bash
tmsh create ltm profile tcp /Common/tcp_lan \
    defaults-from /Common/tcp-lan-optimized \
    nagle disabled \
    delayed-acks disabled
```

## Key TCP Profile Settings

### Window Scaling
```bash
tmsh modify ltm profile tcp /Common/custom_tcp \
    receive-window-size 65535 \
    send-buffer-size 65535
```

### Congestion Control
```bash
# Options: high-speed, reno, scalable, none, illinois, woodside, westwood
tmsh modify ltm profile tcp /Common/custom_tcp \
    congestion-control woodside
```

### Nagle Algorithm
```bash
# Disable for latency-sensitive applications
tmsh modify ltm profile tcp /Common/custom_tcp \
    nagle disabled
```

### Selective Acknowledgments (SACK)
```bash
tmsh modify ltm profile tcp /Common/custom_tcp \
    selective-acks enabled
```

### Initial Congestion Window
```bash
# Increase for faster initial throughput
tmsh modify ltm profile tcp /Common/custom_tcp \
    init-cwnd 10 \
    init-rwnd 10
```

## FastL4 Profile (Layer 4 Pass-through)

### Create FastL4 Profile
```bash
tmsh create ltm profile fastl4 /Common/fast_l4 \
    defaults-from /Common/fastL4 \
    idle-timeout 300 \
    tcp-handshake-timeout 5 \
    loose-close enabled \
    loose-initialization enabled
```

### Apply to Virtual Server
```bash
tmsh create ltm virtual /Common/fast_vs \
    destination 10.0.0.100:0 \
    ip-protocol tcp \
    pool /Common/my_pool \
    profiles add { /Common/fast_l4 }
```

## OneConnect (Connection Pooling)

### Create OneConnect Profile
```bash
tmsh create ltm profile one-connect /Common/oneconnect_custom \
    defaults-from /Common/oneconnect \
    max-size 10000 \
    max-age 86400 \
    max-reuse 1000 \
    idle-timeout-override 60
```

### Apply to Virtual Server
```bash
tmsh modify ltm virtual /Common/web_vs \
    profiles add { /Common/oneconnect_custom }
```

## HTTP Optimization

### HTTP Compression
```bash
tmsh create ltm profile http-compression /Common/compress_custom \
    defaults-from /Common/httpcompression \
    content-type-include add { "text/html" "application/json" "text/css" "application/javascript" } \
    keep-accept-encoding disabled
```

### HTTP Caching (RAM Cache)
```bash
tmsh create ltm profile web-acceleration /Common/cache_custom \
    defaults-from /Common/webacceleration \
    cache-max-entries 10000 \
    cache-size 100mb \
    cache-object-max-size 50000
```

### HTTP Profile Optimization
```bash
tmsh create ltm profile http /Common/http_optimized \
    defaults-from /Common/http \
    insert-xforwarded-for enabled \
    oneconnect-transformations enabled \
    server-agent-name "BIG-IP" \
    max-header-count 64 \
    max-header-size 32768
```

## TMM Performance Tuning

### HT-Split (Hyper-Threading)
```bash
# Enable HT-Split for HT-enabled CPUs
tmsh modify sys db tmm.ht.split value enable

# Reboot required
tmsh reboot
```

### CPU Affinity
```bash
# Check current TMM assignment
tmsh show sys tmm-info

# View CPU utilization per TMM
tmsh show sys performance raw
```

## Connection Limits

### Virtual Server Connection Limit
```bash
tmsh modify ltm virtual /Common/web_vs \
    connection-limit 10000
```

### Pool Member Connection Limit
```bash
tmsh modify ltm pool /Common/web_pool \
    members modify { 10.0.0.10:80 { connection-limit 1000 } }
```

### Rate Limiting (iRule)
```tcl
when CLIENT_ACCEPTED {
    set client_ip [IP::client_addr]
    set conn_count [table incr -subtable conn_limit $client_ip]
    
    if { $conn_count == 1 } {
        table timeout -subtable conn_limit $client_ip 60
    }
    
    if { $conn_count > 100 } {
        reject
    }
}

when CLIENT_CLOSED {
    table decr -subtable conn_limit [IP::client_addr]
}
```

## Bandwidth Management

### Rate Class
```bash
tmsh create net rate-shaping class /Common/rate_1mbps \
    rate 1000000 \
    ceiling 1500000 \
    burst-size 15000
```

### Apply Rate Class via iRule
```tcl
when HTTP_REQUEST {
    if { [IP::client_addr] starts_with "192.168.1." } {
        RATECLASS::client /Common/rate_1mbps
    }
}
```

## Performance Monitoring

### View Performance Statistics
```bash
tmsh show sys performance all-stats
tmsh show sys performance throughput
tmsh show sys performance connections
```

### TMM Statistics
```bash
tmsh show sys tmm-info
tmsh show sys tmm-traffic
```

### Virtual Server Statistics
```bash
tmsh show ltm virtual /Common/web_vs stats
```

### Connection Table Size
```bash
tmsh show sys connection count
```

## Performance Troubleshooting

### High CPU
```bash
# Check per-TMM CPU
tmsh show sys tmm-info

# Check iRule execution time
tmsh show ltm rule /Common/my_irule

# Profile traffic
tcpdump -ni 0.0 -c 10000 -w /var/tmp/sample.pcap
```

### Connection Issues
```bash
# Check connection table
tmsh show sys connection count

# Check memory usage
tmsh show sys memory

# Check SNAT port exhaustion
tmsh show ltm snatpool /Common/my_snatpool members
```

### Timeout Issues
```bash
# Verify idle timeout
tmsh list ltm profile tcp /Common/custom_tcp idle-timeout

# Check connection state
tmsh show sys connection cs-client-addr 10.0.0.100
```

## Best Practices

1. **Use appropriate profiles**
   - FastL4 for L4 pass-through (highest performance)
   - Standard TCP profile for full proxy
   - WAN-optimized for high-latency links

2. **Enable OneConnect** for HTTP applications

3. **Tune TCP windows** for high-bandwidth links

4. **Disable Nagle** for latency-sensitive applications

5. **Set appropriate idle timeouts** to balance resource usage

6. **Monitor TMM utilization** and distribute load

7. **Use connection limits** to protect backend servers

8. **Enable compression** for compressible content types
