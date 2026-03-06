# F5 BIG-IP LTM Fundamentals

## Architecture Overview

### Full Proxy Architecture
BIG-IP operates as a full proxy, maintaining separate client-side and server-side connections:
- Client connects to virtual server (VIP)
- BIG-IP terminates client connection
- BIG-IP initiates new connection to pool member
- Enables complete traffic inspection and manipulation

### TMM (Traffic Management Microkernel)
- Core packet processing engine
- Runs in user space for stability
- Multi-threaded: one TMM process per CPU core
- Handles all data plane traffic

### TMM HT-Split
- Hyper-Threading optimization
- Dedicates logical cores to specific tasks
- Improves performance on HT-enabled CPUs
- Configure via `tmsh modify sys db tmm.ht.split value enable`

## Virtual Server Types

### Standard Virtual Server
```bash
tmsh create ltm virtual /Common/my_vs \
    destination 10.0.0.100:443 \
    ip-protocol tcp \
    pool /Common/my_pool \
    profiles add { /Common/tcp /Common/http /Common/clientssl }
```

### Performance (Layer 4)
```bash
tmsh create ltm virtual /Common/fast_vs \
    destination 10.0.0.100:0 \
    ip-protocol tcp \
    pool /Common/my_pool \
    profiles add { /Common/fastL4 }
```

### Forwarding (IP)
```bash
tmsh create ltm virtual /Common/forward_vs \
    destination 0.0.0.0/0:0 \
    ip-forward \
    vlans-enabled vlans add { internal }
```

### Reject
```bash
tmsh create ltm virtual /Common/reject_vs \
    destination 10.0.0.100:8080 \
    reject
```

## Pool Configuration

### Basic Pool with Members
```bash
tmsh create ltm pool /Common/web_pool \
    members add { 
        192.168.1.10:80 
        192.168.1.11:80 
        192.168.1.12:80 
    } \
    monitor /Common/http
```

### Priority Group Activation
```bash
tmsh create ltm pool /Common/priority_pool \
    members add { 
        192.168.1.10:80 { priority-group 10 } 
        192.168.1.11:80 { priority-group 10 } 
        192.168.1.20:80 { priority-group 5 } 
    } \
    min-active-members 1
```

## Load Balancing Methods

| Method | Command | Use Case |
|--------|---------|----------|
| Round Robin | `load-balancing-mode round-robin` | Default, equal distribution |
| Ratio | `load-balancing-mode ratio-member` | Weighted distribution |
| Least Connections | `load-balancing-mode least-connections-member` | Uneven request durations |
| Fastest | `load-balancing-mode fastest-node` | Response time sensitive |
| Observed | `load-balancing-mode observed-member` | Dynamic weighting |
| Predictive | `load-balancing-mode predictive-member` | Trend analysis |

## Health Monitors

### HTTP Monitor
```bash
tmsh create ltm monitor http /Common/my_http_monitor \
    defaults-from /Common/http \
    interval 5 \
    timeout 16 \
    send "GET /health HTTP/1.1\r\nHost: myapp.com\r\nConnection: close\r\n\r\n" \
    recv "200 OK"
```

### TCP Half-Open
```bash
tmsh create ltm monitor tcp-half-open /Common/my_tcp_monitor \
    defaults-from /Common/tcp_half_open \
    interval 5 \
    timeout 16
```

### HTTPS Monitor
```bash
tmsh create ltm monitor https /Common/my_https_monitor \
    defaults-from /Common/https \
    cert /Common/default.crt \
    key /Common/default.key \
    send "GET /health HTTP/1.1\r\nHost: myapp.com\r\n\r\n" \
    recv "healthy"
```

## Persistence Profiles

### Source Address Persistence
```bash
tmsh create ltm persistence source-addr /Common/src_persist \
    defaults-from /Common/source_addr \
    timeout 300 \
    mask 255.255.255.255
```

### Cookie Persistence
```bash
tmsh create ltm persistence cookie /Common/cookie_persist \
    defaults-from /Common/cookie \
    cookie-name "SERVERID" \
    method insert \
    expiration 0
```

### Universal Persistence
```bash
tmsh create ltm persistence universal /Common/custom_persist \
    defaults-from /Common/universal \
    rule /Common/my_persist_irule
```

## SNAT Configuration

### SNAT Pool
```bash
tmsh create ltm snatpool /Common/my_snatpool \
    members add { 10.0.0.200 10.0.0.201 }

tmsh modify ltm virtual /Common/my_vs \
    source-address-translation { type snat pool /Common/my_snatpool }
```

### Auto Map
```bash
tmsh modify ltm virtual /Common/my_vs \
    source-address-translation { type automap }
```

## OneConnect (Connection Pooling)
```bash
tmsh create ltm profile one-connect /Common/my_oneconnect \
    defaults-from /Common/oneconnect \
    max-size 10000 \
    max-age 86400 \
    max-reuse 1000

tmsh modify ltm virtual /Common/my_vs \
    profiles add { /Common/my_oneconnect }
```

## iRules Basics

### HTTP Redirect
```tcl
when HTTP_REQUEST {
    if { [HTTP::host] eq "old.example.com" } {
        HTTP::redirect "https://new.example.com[HTTP::uri]"
    }
}
```

### Header Insertion
```tcl
when HTTP_REQUEST {
    HTTP::header insert "X-Forwarded-For" [IP::client_addr]
    HTTP::header insert "X-Real-IP" [IP::client_addr]
}
```

### Pool Selection
```tcl
when HTTP_REQUEST {
    switch -glob [HTTP::uri] {
        "/api/*" { pool api_pool }
        "/static/*" { pool static_pool }
        default { pool default_pool }
    }
}
```

## Common Troubleshooting Commands

```bash
# Show virtual server status
tmsh show ltm virtual

# Show pool member status
tmsh show ltm pool members

# Show active connections
tmsh show sys connection

# Show persistence records
tmsh show ltm persistence persist-records

# Show interface statistics
tmsh show net interface
```
