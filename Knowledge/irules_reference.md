# F5 iRules Reference Guide

## iRule Structure

```tcl
when <EVENT> [priority <number>] {
    # TCL code
}
```

## Common Events

### Layer 4 Events
| Event | Description | Use Case |
|-------|-------------|----------|
| CLIENT_ACCEPTED | Client TCP connection established | Connection tracking, logging |
| CLIENT_CLOSED | Client connection closed | Cleanup |
| SERVER_CONNECTED | Server TCP connection established | Server-side operations |
| SERVER_CLOSED | Server connection closed | Cleanup |
| CLIENT_DATA | Data received from client (requires TCP::collect) | Raw data inspection |
| SERVER_DATA | Data received from server (requires TCP::collect) | Raw data modification |

### HTTP Events
| Event | Description | Use Case |
|-------|-------------|----------|
| HTTP_REQUEST | HTTP request received | URL routing, header manipulation |
| HTTP_REQUEST_SEND | Request about to be sent to server | Final modifications |
| HTTP_RESPONSE | Response headers received | Header inspection/modification |
| HTTP_RESPONSE_DATA | Response body chunks received | Body modification |

### SSL Events
| Event | Description | Use Case |
|-------|-------------|----------|
| CLIENTSSL_HANDSHAKE | Client SSL handshake complete | Certificate inspection |
| CLIENTSSL_CLIENTCERT | Client certificate received | mTLS validation |
| SERVERSSL_HANDSHAKE | Server SSL handshake complete | Server cert validation |

## HTTP Commands

### Request Inspection
```tcl
when HTTP_REQUEST {
    # Get request components
    set uri [HTTP::uri]
    set path [HTTP::path]
    set query [HTTP::query]
    set method [HTTP::method]
    set host [HTTP::host]
    set version [HTTP::version]
    
    # Get specific header
    set auth [HTTP::header value "Authorization"]
    
    # Check if header exists
    if { [HTTP::header exists "X-Custom-Header"] } {
        # do something
    }
    
    # Get all headers
    foreach header [HTTP::header names] {
        log local0. "$header: [HTTP::header value $header]"
    }
}
```

### Request Modification
```tcl
when HTTP_REQUEST {
    # Insert header
    HTTP::header insert "X-Forwarded-For" [IP::client_addr]
    
    # Replace header
    HTTP::header replace "Host" "backend.example.com"
    
    # Remove header
    HTTP::header remove "X-Debug"
    
    # Modify URI
    HTTP::uri "/api/v2[HTTP::uri]"
    
    # Modify path only
    HTTP::path "/newpath[HTTP::path]"
}
```

### Response Handling
```tcl
when HTTP_RESPONSE {
    # Get response code
    set status [HTTP::status]
    
    # Modify response header
    HTTP::header insert "X-Server" "BIG-IP"
    HTTP::header remove "Server"
    
    # Collect response body for modification
    if { [HTTP::header value "Content-Type"] contains "text/html" } {
        HTTP::collect [HTTP::header value "Content-Length"]
    }
}

when HTTP_RESPONSE_DATA {
    # Modify response body
    set payload [HTTP::payload]
    set modified [string map {"old" "new"} $payload]
    HTTP::payload replace 0 [HTTP::payload length] $modified
}
```

### Redirects
```tcl
when HTTP_REQUEST {
    # Simple redirect
    HTTP::redirect "https://[HTTP::host][HTTP::uri]"
    
    # Conditional redirect
    if { [HTTP::host] eq "old.example.com" } {
        HTTP::redirect "https://new.example.com[HTTP::uri]"
    }
}
```

### Respond Directly
```tcl
when HTTP_REQUEST {
    # Return custom response
    HTTP::respond 503 content "Service Unavailable" \
        "Content-Type" "text/plain"
    
    # Return JSON
    HTTP::respond 200 content {{"status":"ok"}} \
        "Content-Type" "application/json"
    
    # Return with headers
    HTTP::respond 301 "Location" "https://new.example.com[HTTP::uri]"
}
```

## Pool Selection

### Basic Pool Selection
```tcl
when HTTP_REQUEST {
    # Static pool selection
    pool /Common/web_pool
    
    # Based on URI
    switch -glob [HTTP::uri] {
        "/api/*" { pool /Common/api_pool }
        "/static/*" { pool /Common/static_pool }
        "/admin/*" { pool /Common/admin_pool }
        default { pool /Common/default_pool }
    }
}
```

### Pool Member Selection
```tcl
when HTTP_REQUEST {
    # Select specific member
    pool /Common/web_pool member 10.0.0.10 80
    
    # Conditional member selection
    if { [active_members /Common/web_pool] < 1 } {
        pool /Common/backup_pool
    }
}
```

### Node Selection
```tcl
when HTTP_REQUEST {
    # Direct to specific node (bypasses pool)
    node 10.0.0.10 80
}
```

## Persistence

### Set Persistence
```tcl
when HTTP_REQUEST {
    # Use cookie value for persistence
    persist uie [HTTP::cookie value "JSESSIONID"]
    
    # Use header for persistence
    persist uie [HTTP::header value "X-User-ID"]
}
```

### Manual Persistence
```tcl
when HTTP_REQUEST {
    # Check for existing session
    set persist_key [HTTP::cookie value "session_id"]
    if { [persist lookup uie $persist_key] ne "" } {
        persist uie $persist_key
    }
}
```

## Connection Commands

### TCP Operations
```tcl
when CLIENT_ACCEPTED {
    # Get client info
    set client_ip [IP::client_addr]
    set client_port [TCP::client_port]
    set server_ip [IP::server_addr]
    
    # Collect data (for layer 4 inspection)
    TCP::collect
}

when CLIENT_DATA {
    # Get collected data
    set data [TCP::payload]
    
    # Release data to continue
    TCP::release
}
```

### Connection Limits
```tcl
when CLIENT_ACCEPTED {
    # Limit connections per client
    set client_ip [IP::client_addr]
    set conn_count [table incr -subtable conn_limit $client_ip]
    
    if { $conn_count > 100 } {
        reject
    }
    
    # Set TTL for counter
    table timeout -subtable conn_limit $client_ip 60
}

when CLIENT_CLOSED {
    table decr -subtable conn_limit [IP::client_addr]
}
```

## Data Groups

### Using Data Groups
```tcl
when HTTP_REQUEST {
    # String data group
    if { [class match [IP::client_addr] equals blocked_ips] } {
        reject
    }
    
    # Key-value lookup
    set backend [class match -value [HTTP::host] equals host_to_pool]
    if { $backend ne "" } {
        pool $backend
    }
}
```

### Create Data Group
```bash
tmsh create ltm data-group internal blocked_ips \
    records add { 
        192.168.1.100 { } 
        10.0.0.0/8 { } 
    } \
    type ip

tmsh create ltm data-group internal host_to_pool \
    records add { 
        "api.example.com" { data "/Common/api_pool" }
        "web.example.com" { data "/Common/web_pool" }
    } \
    type string
```

## Tables (Session Variables)

### Table Operations
```tcl
# Set value with timeout
table set -subtable my_table "key1" "value1" 300

# Get value
set val [table lookup -subtable my_table "key1"]

# Increment counter
set count [table incr -subtable counters $client_ip]

# Delete entry
table delete -subtable my_table "key1"

# Check if key exists
if { [table lookup -notouch -subtable my_table "key1"] ne "" } {
    # key exists
}
```

### Rate Limiting Example
```tcl
when HTTP_REQUEST {
    set client_ip [IP::client_addr]
    set requests [table incr -subtable rate_limit $client_ip]
    
    if { $requests == 1 } {
        # First request, set 60 second window
        table timeout -subtable rate_limit $client_ip 60
    }
    
    if { $requests > 100 } {
        # Over 100 requests per minute
        HTTP::respond 429 content "Rate limit exceeded"
    }
}
```

## SSL/TLS Commands

### Client Certificate Inspection
```tcl
when CLIENTSSL_CLIENTCERT {
    # Get certificate details
    set cert [SSL::cert 0]
    set subject [X509::subject $cert]
    set issuer [X509::issuer $cert]
    set cn [X509::subject $cert [X509::subject_name $cert cn]]
    
    log local0. "Client cert CN: $cn"
}

when HTTP_REQUEST {
    # Access cert info (set in CLIENTSSL_CLIENTCERT)
    if { [info exists cn] && $cn ne "" } {
        HTTP::header insert "X-Client-CN" $cn
    }
}
```

### SSL Session Info
```tcl
when CLIENTSSL_HANDSHAKE {
    set ssl_cipher [SSL::cipher name]
    set ssl_version [SSL::cipher version]
    log local0. "SSL: $ssl_version - $ssl_cipher"
}
```

## Logging

### Basic Logging
```tcl
when HTTP_REQUEST {
    # Log levels: emerg, alert, crit, err, warning, notice, info, debug
    log local0. "Request from [IP::client_addr] to [HTTP::host][HTTP::uri]"
    log local0.warning "Warning message"
    log local0.debug "Debug info"
}
```

### High-Speed Logging (HSL)
```tcl
when CLIENT_ACCEPTED {
    set hsl [HSL::open -proto UDP -pool /Common/syslog_pool]
}

when HTTP_REQUEST {
    set log_msg "src=[IP::client_addr] host=[HTTP::host] uri=[HTTP::uri]"
    HSL::send $hsl $log_msg
}
```

## Error Handling

```tcl
when HTTP_REQUEST {
    # Try-catch block
    if { [catch {
        set user_id [HTTP::header value "X-User-ID"]
        if { $user_id eq "" } {
            error "Missing user ID"
        }
    } err] } {
        log local0.error "Error: $err"
        HTTP::respond 400 content "Bad Request: $err"
    }
}
```

## Common Patterns

### URL Rewriting
```tcl
when HTTP_REQUEST {
    # /old/* -> /new/*
    if { [HTTP::uri] starts_with "/old/" } {
        HTTP::uri [string map {"/old/" "/new/"} [HTTP::uri]]
    }
}
```

### A/B Testing
```tcl
when CLIENT_ACCEPTED {
    # Assign to bucket based on IP hash
    set bucket [expr { [IP::client_addr] % 100 }]
    if { $bucket < 10 } {
        # 10% to test pool
        pool /Common/test_pool
    } else {
        pool /Common/production_pool
    }
}
```

### Maintenance Mode
```tcl
when HTTP_REQUEST {
    if { [active_members /Common/web_pool] < 1 } {
        HTTP::respond 503 content "<h1>Maintenance</h1>" \
            "Content-Type" "text/html" \
            "Retry-After" "3600"
    }
}
```

### Add Client IP Header
```tcl
when HTTP_REQUEST {
    # Remove any existing headers (prevent spoofing)
    HTTP::header remove "X-Forwarded-For"
    HTTP::header remove "X-Real-IP"
    
    # Insert real client IP
    HTTP::header insert "X-Forwarded-For" [IP::client_addr]
    HTTP::header insert "X-Real-IP" [IP::client_addr]
}
```

## Performance Tips

1. **Minimize logging** - Use HSL for high-traffic scenarios
2. **Use data groups** - Faster than inline conditionals
3. **Avoid regex** - Use string commands when possible
4. **Cache lookups** - Store repeated lookups in variables
5. **Use switch** - More efficient than multiple if/elseif
6. **Exit early** - Return/reject as soon as possible

## Testing iRules

```bash
# Check syntax
tmsh load sys config verify file /var/tmp/my_irule.tcl

# View iRule statistics
tmsh show ltm rule /Common/my_irule

# Reset iRule statistics
tmsh reset-stats ltm rule /Common/my_irule
```
