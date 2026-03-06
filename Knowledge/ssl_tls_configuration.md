# F5 BIG-IP SSL/TLS Configuration Guide

## SSL Offloading Architecture

```
Client ──[HTTPS]──> BIG-IP ──[HTTP]──> Server
                     │
              SSL Termination
              (Client SSL Profile)
```

## SSL Bridging Architecture

```
Client ──[HTTPS]──> BIG-IP ──[HTTPS]──> Server
                     │
          Client SSL    Server SSL
          Profile       Profile
```

## Certificate Management

### Import Certificate via TMSH
```bash
# Upload cert file to /var/tmp/ first, then:
tmsh install sys crypto cert my_cert from-local-file /var/tmp/cert.crt

# Import key
tmsh install sys crypto key my_key from-local-file /var/tmp/key.key

# Import CA bundle/chain
tmsh install sys crypto cert my_chain from-local-file /var/tmp/chain.crt
```

### Generate Self-Signed Certificate
```bash
tmsh create sys crypto key my_selfsigned gen-certificate \
    common-name "www.example.com" \
    country US \
    state WA \
    city Seattle \
    organization "Example Inc" \
    ou IT \
    key-size 2048 \
    lifetime 365
```

### Create CSR
```bash
tmsh create sys crypto csr my_csr \
    key /Common/my_key \
    common-name "www.example.com" \
    country US \
    state WA \
    city Seattle \
    organization "Example Inc"
```

### View Certificate Details
```bash
tmsh list sys crypto cert my_cert
tmsh run sys crypto check-cert certificate /Common/my_cert
```

## Client SSL Profile

### Basic Client SSL Profile
```bash
tmsh create ltm profile client-ssl /Common/my_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/my_cert.crt \
    key /Common/my_key.key \
    chain /Common/my_chain.crt
```

### Client SSL with SNI
```bash
tmsh create ltm profile client-ssl /Common/sni_clientssl \
    defaults-from /Common/clientssl \
    cert-key-chain add { 
        default { 
            cert /Common/default.crt 
            key /Common/default.key 
        } 
    } \
    sni-default true \
    server-name www.example.com

# Add SNI cert
tmsh modify ltm profile client-ssl /Common/sni_clientssl \
    cert-key-chain add { 
        api_example { 
            cert /Common/api_example.crt 
            key /Common/api_example.key 
        } 
    }
```

### Client SSL with Mutual TLS (mTLS)
```bash
tmsh create ltm profile client-ssl /Common/mtls_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/server.crt \
    key /Common/server.key \
    ca-file /Common/client_ca.crt \
    client-cert-ca /Common/client_ca.crt \
    peer-cert-mode require \
    authenticate once \
    authenticate-depth 2
```

### Cipher String Configuration
```bash
# Modern secure ciphers (TLS 1.2+)
tmsh create ltm profile client-ssl /Common/secure_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/my_cert.crt \
    key /Common/my_key.key \
    options { dont-insert-empty-fragments no-tlsv1 no-tlsv1.1 } \
    ciphers "ECDHE+AESGCM:DHE+AESGCM:ECDHE+AES256:DHE+AES256:!aNULL:!MD5:!DSS"

# TLS 1.3 only
tmsh modify ltm profile client-ssl /Common/secure_clientssl \
    options add { no-tlsv1 no-tlsv1.1 no-tlsv1.2 }
```

### Cipher Groups (v14.0+)
```bash
tmsh list ltm cipher group
tmsh list ltm cipher rule

# Use built-in cipher group
tmsh create ltm profile client-ssl /Common/modern_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/my_cert.crt \
    key /Common/my_key.key \
    cipher-group /Common/f5-secure
```

## Server SSL Profile

### Basic Server SSL Profile
```bash
tmsh create ltm profile server-ssl /Common/my_serverssl \
    defaults-from /Common/serverssl \
    server-name example.com
```

### Server SSL with Server Certificate Verification
```bash
tmsh create ltm profile server-ssl /Common/verify_serverssl \
    defaults-from /Common/serverssl \
    ca-file /Common/trusted_ca.crt \
    peer-cert-mode require \
    authenticate always \
    authenticate-depth 2 \
    server-name backend.example.com
```

### Server SSL with Client Certificate
```bash
tmsh create ltm profile server-ssl /Common/mtls_serverssl \
    defaults-from /Common/serverssl \
    cert /Common/client_cert.crt \
    key /Common/client_key.key \
    chain /Common/client_chain.crt \
    server-name backend.example.com
```

## Apply SSL Profiles to Virtual Server

### SSL Offloading
```bash
tmsh create ltm virtual /Common/https_vs \
    destination 10.0.0.100:443 \
    ip-protocol tcp \
    pool /Common/web_pool \
    profiles add { 
        /Common/tcp 
        /Common/http 
        /Common/my_clientssl { context clientside } 
    }
```

### SSL Bridging (Re-encryption)
```bash
tmsh create ltm virtual /Common/ssl_bridge_vs \
    destination 10.0.0.100:443 \
    ip-protocol tcp \
    pool /Common/ssl_pool \
    profiles add { 
        /Common/tcp 
        /Common/http 
        /Common/my_clientssl { context clientside } 
        /Common/my_serverssl { context serverside } 
    }
```

## SSL Session Caching

```bash
tmsh modify ltm profile client-ssl /Common/my_clientssl \
    cache-size 262144 \
    cache-timeout 3600
```

## OCSP Stapling

```bash
# Create OCSP validator
tmsh create ltm profile ocsp-stapling-params /Common/my_ocsp \
    dns-resolver /Common/f5-aws-dns \
    sign-hash sha256 \
    trusted-ca /Common/trusted_ca.crt

# Apply to client SSL profile
tmsh modify ltm profile client-ssl /Common/my_clientssl \
    ocsp-stapling enabled \
    ocsp-stapling-profile /Common/my_ocsp
```

## Certificate Revocation

### CRL-Based Revocation
```bash
tmsh create ltm profile client-ssl /Common/crl_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/server.crt \
    key /Common/server.key \
    crl-file /Common/my_crl.crl
```

### OCSP-Based Revocation
```bash
tmsh create ltm profile client-ssl /Common/ocsp_clientssl \
    defaults-from /Common/clientssl \
    cert /Common/server.crt \
    key /Common/server.key \
    authenticate once \
    peer-cert-mode require \
    ca-file /Common/client_ca.crt \
    client-cert-ca /Common/client_ca.crt
```

## SSL Troubleshooting

### Check Certificate Expiry
```bash
tmsh run sys crypto check-cert certificate /Common/my_cert

# List all certs with expiry
for cert in $(tmsh list sys crypto cert one-line | awk '{print $4}'); do 
    echo "=== $cert ===" 
    tmsh run sys crypto check-cert certificate $cert 2>/dev/null | grep -E "Cert|Not After"
done
```

### Debug SSL Handshake
```bash
# Enable SSL debug logging
tmsh modify sys db log.ssl.level value debug

# View logs
tail -f /var/log/ltm | grep -i ssl

# Disable debug logging
tmsh modify sys db log.ssl.level value warning
```

### tcpdump for SSL Analysis
```bash
# Capture SSL traffic on interface
tcpdump -ni 1.1 port 443 -w /var/tmp/ssl_capture.pcap

# Capture with pre-master secret (for Wireshark decryption)
ssldump -Aed -nr /var/tmp/ssl_capture.pcap
```

### Verify Cipher Negotiation
```bash
# From external system
openssl s_client -connect bigip.example.com:443 -tls1_2

# Check specific cipher
openssl s_client -connect bigip.example.com:443 -cipher ECDHE-RSA-AES256-GCM-SHA384
```

### SSL Statistics
```bash
tmsh show ltm profile client-ssl /Common/my_clientssl stats
tmsh show sys performance ssl
```

## Common SSL Issues

### Certificate Chain Issues
```bash
# Verify chain is complete
openssl verify -CAfile /var/tmp/chain.crt /var/tmp/cert.crt

# Check chain order (should be: cert -> intermediate -> root)
openssl s_client -connect bigip.example.com:443 -showcerts
```

### Key Mismatch
```bash
# Compare cert and key modulus
openssl x509 -noout -modulus -in cert.crt | md5sum
openssl rsa -noout -modulus -in key.key | md5sum
# Outputs should match
```

### TLS Version Issues
```bash
# Test specific TLS version
openssl s_client -connect bigip.example.com:443 -tls1_2
openssl s_client -connect bigip.example.com:443 -tls1_3

# Disable older TLS versions
tmsh modify ltm profile client-ssl /Common/my_clientssl \
    options add { no-sslv3 no-tlsv1 no-tlsv1.1 }
```

## iRule SSL Examples

### Log Client Certificate DN
```tcl
when CLIENTSSL_CLIENTCERT {
    set cert_dn [X509::subject [SSL::cert 0]]
    log local0. "Client cert DN: $cert_dn"
}
```

### Reject Based on Client Cert
```tcl
when CLIENTSSL_CLIENTCERT {
    set cn [X509::subject [SSL::cert 0]]
    if { !($cn contains "allowed-client") } {
        reject
    }
}
```

### Select Pool Based on SNI
```tcl
when CLIENT_ACCEPTED {
    TCP::collect
}

when CLIENT_DATA {
    binary scan [TCP::payload] cSS rtype len1 len2
    if { $rtype == 22 } {
        set sni_start [expr {43 + [binary scan [TCP::payload] @43c sessid_len; set sessid_len]}]
        # Parse SNI from ClientHello...
    }
    TCP::release
}
```
