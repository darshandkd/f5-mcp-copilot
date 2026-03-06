# F5 iControl REST API Reference

## Base URL Format
```
https://<bigip-address>/mgmt/tm/<module>/<component>
```

## Authentication

### Basic Auth
```bash
curl -sk -u admin:password https://bigip.example.com/mgmt/tm/ltm/pool
```

### Token-Based Auth
```bash
# Get token
curl -sk -X POST https://bigip.example.com/mgmt/shared/authn/login \
    -H "Content-Type: application/json" \
    -d '{"username":"admin","password":"password","loginProviderName":"tmos"}'

# Use token
curl -sk https://bigip.example.com/mgmt/tm/ltm/pool \
    -H "X-F5-Auth-Token: <token>"
```

## Common Endpoints

| Resource | Endpoint |
|----------|----------|
| Virtual Servers | `/mgmt/tm/ltm/virtual` |
| Pools | `/mgmt/tm/ltm/pool` |
| Pool Members | `/mgmt/tm/ltm/pool/~Common~<pool>/members` |
| Nodes | `/mgmt/tm/ltm/node` |
| Monitors | `/mgmt/tm/ltm/monitor/<type>` |
| Profiles | `/mgmt/tm/ltm/profile/<type>` |
| iRules | `/mgmt/tm/ltm/rule` |
| Self IPs | `/mgmt/tm/net/self` |
| VLANs | `/mgmt/tm/net/vlan` |
| Routes | `/mgmt/tm/net/route` |
| Certificates | `/mgmt/tm/sys/crypto/cert` |
| HA Status | `/mgmt/tm/cm/device` |
| System Info | `/mgmt/tm/sys/version` |

## HTTP Methods

| Method | Purpose |
|--------|---------|
| GET | Retrieve configuration |
| POST | Create new object |
| PUT | Replace entire object |
| PATCH | Modify specific properties |
| DELETE | Remove object |

## Virtual Server Operations

### List All Virtual Servers
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/virtual
```

### Get Specific Virtual Server
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/virtual/~Common~my_vs
```

### Create Virtual Server
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/virtual \
    -H "Content-Type: application/json" \
    -d '{
        "name": "web_vs",
        "partition": "Common",
        "destination": "/Common/10.0.0.100:443",
        "ipProtocol": "tcp",
        "pool": "/Common/web_pool",
        "profiles": [
            {"name": "/Common/tcp"},
            {"name": "/Common/http"},
            {"name": "/Common/clientssl", "context": "clientside"}
        ]
    }'
```

### Modify Virtual Server
```bash
curl -sk -u admin:password \
    -X PATCH https://bigip.example.com/mgmt/tm/ltm/virtual/~Common~web_vs \
    -H "Content-Type: application/json" \
    -d '{"pool": "/Common/new_pool"}'
```

### Delete Virtual Server
```bash
curl -sk -u admin:password \
    -X DELETE https://bigip.example.com/mgmt/tm/ltm/virtual/~Common~web_vs
```

## Pool Operations

### List All Pools
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/pool
```

### Create Pool with Members
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/pool \
    -H "Content-Type: application/json" \
    -d '{
        "name": "web_pool",
        "partition": "Common",
        "loadBalancingMode": "round-robin",
        "monitor": "/Common/http",
        "members": [
            {"name": "server1:80", "address": "10.0.0.10"},
            {"name": "server2:80", "address": "10.0.0.11"}
        ]
    }'
```

### Get Pool Members
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members
```

### Add Pool Member
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members \
    -H "Content-Type: application/json" \
    -d '{"name": "server3:80", "address": "10.0.0.12"}'
```

### Disable Pool Member
```bash
curl -sk -u admin:password \
    -X PATCH https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members/~Common~server1:80 \
    -H "Content-Type: application/json" \
    -d '{"state": "user-disabled"}'
```

### Force Pool Member Offline
```bash
curl -sk -u admin:password \
    -X PATCH https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members/~Common~server1:80 \
    -H "Content-Type: application/json" \
    -d '{"state": "user-down"}'
```

### Delete Pool Member
```bash
curl -sk -u admin:password \
    -X DELETE https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members/~Common~server3:80
```

## Monitor Operations

### Create HTTP Monitor
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/monitor/http \
    -H "Content-Type: application/json" \
    -d '{
        "name": "custom_http",
        "partition": "Common",
        "defaultsFrom": "/Common/http",
        "interval": 10,
        "timeout": 31,
        "send": "GET /health HTTP/1.1\r\nHost: example.com\r\n\r\n",
        "recv": "200 OK"
    }'
```

### Create HTTPS Monitor
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/monitor/https \
    -H "Content-Type: application/json" \
    -d '{
        "name": "custom_https",
        "partition": "Common",
        "defaultsFrom": "/Common/https",
        "interval": 10,
        "timeout": 31,
        "send": "GET /health HTTP/1.1\r\nHost: example.com\r\n\r\n",
        "recv": "healthy"
    }'
```

## Profile Operations

### Create TCP Profile
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/profile/tcp \
    -H "Content-Type: application/json" \
    -d '{
        "name": "custom_tcp",
        "partition": "Common",
        "defaultsFrom": "/Common/tcp",
        "idleTimeout": 300
    }'
```

### Create HTTP Profile
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/profile/http \
    -H "Content-Type: application/json" \
    -d '{
        "name": "custom_http",
        "partition": "Common",
        "defaultsFrom": "/Common/http",
        "insertXforwardedFor": "enabled"
    }'
```

## iRule Operations

### Create iRule
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/rule \
    -H "Content-Type: application/json" \
    -d '{
        "name": "redirect_rule",
        "partition": "Common",
        "apiAnonymous": "when HTTP_REQUEST {\n    HTTP::redirect https://[HTTP::host][HTTP::uri]\n}"
    }'
```

### Get iRule
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/rule/~Common~redirect_rule
```

## SSL/TLS Operations

### Upload Certificate
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/sys/crypto/cert \
    -H "Content-Type: application/json" \
    -d '{
        "command": "install",
        "name": "my_cert",
        "from-local-file": "/var/tmp/cert.crt"
    }'
```

### Create Client SSL Profile
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/ltm/profile/client-ssl \
    -H "Content-Type: application/json" \
    -d '{
        "name": "my_clientssl",
        "partition": "Common",
        "cert": "/Common/my_cert.crt",
        "key": "/Common/my_cert.key",
        "chain": "/Common/my_chain.crt"
    }'
```

## System Operations

### Get System Version
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/sys/version
```

### Get HA Status
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/cm/device
```

### Get Sync Status
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/cm/sync-status
```

### Save Configuration
```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/sys/config \
    -H "Content-Type: application/json" \
    -d '{"command": "save"}'
```

## Statistics Endpoints

### Virtual Server Stats
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/virtual/~Common~web_vs/stats
```

### Pool Stats
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/stats
```

### Pool Member Stats
```bash
curl -sk -u admin:password \
    https://bigip.example.com/mgmt/tm/ltm/pool/~Common~web_pool/members/stats
```

## Query Parameters

### Expand Sub-collections
```bash
curl -sk -u admin:password \
    "https://bigip.example.com/mgmt/tm/ltm/pool?expandSubcollections=true"
```

### Select Specific Fields
```bash
curl -sk -u admin:password \
    "https://bigip.example.com/mgmt/tm/ltm/virtual?\$select=name,destination,pool"
```

### Filter Results
```bash
curl -sk -u admin:password \
    "https://bigip.example.com/mgmt/tm/ltm/virtual?\$filter=partition+eq+Common"
```

## Bash Commands via REST

```bash
curl -sk -u admin:password \
    -X POST https://bigip.example.com/mgmt/tm/util/bash \
    -H "Content-Type: application/json" \
    -d '{"command": "run", "utilCmdArgs": "-c \"tmsh show sys version\""}'
```

## Python Example

```python
import requests
from requests.auth import HTTPBasicAuth
import urllib3
urllib3.disable_warnings()

class F5Client:
    def __init__(self, host, username, password):
        self.base_url = f"https://{host}/mgmt/tm"
        self.auth = HTTPBasicAuth(username, password)
        self.headers = {"Content-Type": "application/json"}
    
    def get(self, endpoint):
        return requests.get(
            f"{self.base_url}/{endpoint}",
            auth=self.auth,
            headers=self.headers,
            verify=False
        ).json()
    
    def post(self, endpoint, data):
        return requests.post(
            f"{self.base_url}/{endpoint}",
            auth=self.auth,
            headers=self.headers,
            json=data,
            verify=False
        ).json()
    
    def patch(self, endpoint, data):
        return requests.patch(
            f"{self.base_url}/{endpoint}",
            auth=self.auth,
            headers=self.headers,
            json=data,
            verify=False
        ).json()
    
    def delete(self, endpoint):
        return requests.delete(
            f"{self.base_url}/{endpoint}",
            auth=self.auth,
            headers=self.headers,
            verify=False
        )

# Usage
client = F5Client("bigip.example.com", "admin", "password")
pools = client.get("ltm/pool")
```
