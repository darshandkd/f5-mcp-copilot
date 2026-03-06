# F5 Automation Toolkit Reference

## Overview

| Tool | Purpose |
|------|---------|
| AS3 | Application Services 3 - Declarative L4-L7 configuration |
| DO | Declarative Onboarding - Device initialization |
| TS | Telemetry Streaming - Metrics and logging export |
| FAST | F5 Application Services Templates - Simplified deployment |

## AS3 (Application Services 3)

### Installation
```bash
# Download AS3 RPM from GitHub releases
# Install via REST API
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/shared/iapp/package-management-tasks \
    -H "Content-Type: application/json" \
    -d '{"operation":"INSTALL","packageFilePath":"/var/tmp/f5-appsvcs.rpm"}'
```

### Verify Installation
```bash
curl -sk -u admin:password \
    https://bigip/mgmt/shared/appsvcs/info
```

### Basic HTTP Application
```json
{
    "class": "AS3",
    "action": "deploy",
    "persist": true,
    "declaration": {
        "class": "ADC",
        "schemaVersion": "3.45.0",
        "Production": {
            "class": "Tenant",
            "WebApp": {
                "class": "Application",
                "serviceMain": {
                    "class": "Service_HTTP",
                    "virtualAddresses": ["10.0.1.100"],
                    "virtualPort": 80,
                    "pool": "web_pool"
                },
                "web_pool": {
                    "class": "Pool",
                    "monitors": ["http"],
                    "members": [{
                        "servicePort": 80,
                        "serverAddresses": ["192.168.1.10", "192.168.1.11"]
                    }]
                }
            }
        }
    }
}
```

### HTTPS with SSL Offload
```json
{
    "class": "AS3",
    "action": "deploy",
    "declaration": {
        "class": "ADC",
        "schemaVersion": "3.45.0",
        "Production": {
            "class": "Tenant",
            "SecureApp": {
                "class": "Application",
                "serviceMain": {
                    "class": "Service_HTTPS",
                    "virtualAddresses": ["10.0.1.100"],
                    "virtualPort": 443,
                    "pool": "web_pool",
                    "serverTLS": "serverTLSProfile"
                },
                "web_pool": {
                    "class": "Pool",
                    "members": [{
                        "servicePort": 80,
                        "serverAddresses": ["192.168.1.10"]
                    }]
                },
                "serverTLSProfile": {
                    "class": "TLS_Server",
                    "certificates": [{"certificate": "tlsCert"}]
                },
                "tlsCert": {
                    "class": "Certificate",
                    "certificate": {"bigip": "/Common/default.crt"},
                    "privateKey": {"bigip": "/Common/default.key"}
                }
            }
        }
    }
}
```

### AS3 with iRule
```json
{
    "class": "Application",
    "serviceMain": {
        "class": "Service_HTTP",
        "virtualAddresses": ["10.0.1.100"],
        "pool": "web_pool",
        "iRules": ["redirectRule"]
    },
    "redirectRule": {
        "class": "iRule",
        "iRule": "when HTTP_REQUEST {\n  HTTP::redirect https://[HTTP::host][HTTP::uri]\n}"
    }
}
```

### Deploy Declaration
```bash
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/shared/appsvcs/declare \
    -H "Content-Type: application/json" \
    -d @declaration.json
```

### Get Current Configuration
```bash
curl -sk -u admin:password \
    https://bigip/mgmt/shared/appsvcs/declare
```

### Delete Tenant
```bash
curl -sk -u admin:password \
    -X DELETE https://bigip/mgmt/shared/appsvcs/declare/Production
```

## Declarative Onboarding (DO)

### DO Declaration Structure
```json
{
    "schemaVersion": "1.0.0",
    "class": "Device",
    "async": true,
    "Common": {
        "class": "Tenant",
        "hostname": "bigip1.example.com",
        "myLicense": {
            "class": "License",
            "licenseType": "regKey",
            "regKey": "XXXXX-XXXXX-XXXXX-XXXXX-XXXXXXX"
        },
        "myDns": {
            "class": "DNS",
            "nameServers": ["8.8.8.8", "8.8.4.4"]
        },
        "myNtp": {
            "class": "NTP",
            "servers": ["0.pool.ntp.org"],
            "timezone": "UTC"
        },
        "myProvisioning": {
            "class": "Provision",
            "ltm": "nominal",
            "asm": "nominal"
        },
        "admin": {
            "class": "User",
            "userType": "regular",
            "password": "secure_password",
            "shell": "bash"
        },
        "external": {
            "class": "VLAN",
            "interfaces": [{"name": "1.1", "tagged": false}]
        },
        "external_self": {
            "class": "SelfIp",
            "address": "10.0.1.10/24",
            "vlan": "external",
            "allowService": "default"
        },
        "default_route": {
            "class": "Route",
            "gw": "10.0.1.1",
            "network": "default"
        }
    }
}
```

### Deploy DO
```bash
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/shared/declarative-onboarding \
    -H "Content-Type: application/json" \
    -d @do-declaration.json
```

### Check DO Status
```bash
curl -sk -u admin:password \
    https://bigip/mgmt/shared/declarative-onboarding
```

## Telemetry Streaming (TS)

### TS Declaration - Splunk
```json
{
    "class": "Telemetry",
    "My_System": {
        "class": "Telemetry_System",
        "systemPoller": {
            "interval": 60
        }
    },
    "My_Listener": {
        "class": "Telemetry_Listener",
        "port": 6514
    },
    "My_Consumer": {
        "class": "Telemetry_Consumer",
        "type": "Splunk",
        "host": "splunk.example.com",
        "protocol": "https",
        "port": 8088,
        "passphrase": {
            "cipherText": "your_splunk_hec_token"
        }
    }
}
```

### TS Declaration - Azure Log Analytics
```json
{
    "class": "Telemetry",
    "My_Consumer": {
        "class": "Telemetry_Consumer",
        "type": "Azure_Log_Analytics",
        "workspaceId": "your-workspace-id",
        "passphrase": {
            "cipherText": "your-shared-key"
        }
    }
}
```

### Deploy TS
```bash
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/shared/telemetry/declare \
    -H "Content-Type: application/json" \
    -d @ts-declaration.json
```

## FAST Templates

### List Available Templates
```bash
curl -sk -u admin:password \
    https://bigip/mgmt/shared/fast/templates
```

### Deploy FAST Application
```bash
curl -sk -u admin:password \
    -X POST https://bigip/mgmt/shared/fast/applications \
    -H "Content-Type: application/json" \
    -d '{
        "name": "myApp",
        "parameters": {
            "tenant_name": "Production",
            "app_name": "WebApp",
            "virtual_address": "10.0.1.100",
            "virtual_port": 80,
            "server_addresses": ["192.168.1.10"]
        }
    }'
```

## Ansible Integration

### Basic Playbook
```yaml
---
- name: Configure F5 BIG-IP
  hosts: f5
  connection: local
  vars:
    provider:
      server: "{{ ansible_host }}"
      user: admin
      password: "{{ admin_password }}"
      validate_certs: no

  tasks:
    - name: Create pool
      f5networks.f5_modules.bigip_pool:
        provider: "{{ provider }}"
        name: web_pool
        lb_method: round-robin
        monitors: /Common/http

    - name: Add pool members
      f5networks.f5_modules.bigip_pool_member:
        provider: "{{ provider }}"
        pool: web_pool
        host: "{{ item }}"
        port: 80
      loop:
        - 192.168.1.10
        - 192.168.1.11

    - name: Create virtual server
      f5networks.f5_modules.bigip_virtual_server:
        provider: "{{ provider }}"
        name: web_vs
        destination: 10.0.1.100
        port: 80
        pool: web_pool
        profiles:
          - http
          - tcp
```

### Ansible AS3 Deployment
```yaml
- name: Deploy AS3 declaration
  f5networks.f5_modules.bigip_as3_deploy:
    provider: "{{ provider }}"
    content: "{{ lookup('file', 'as3-declaration.json') }}"
```

## Python f5-sdk

### Installation
```bash
pip install f5-sdk
```

### Basic Usage
```python
from f5.bigip import ManagementRoot

# Connect
mgmt = ManagementRoot("bigip.example.com", "admin", "password")

# Create pool
pool = mgmt.tm.ltm.pools.pool.create(
    name='web_pool',
    partition='Common'
)

# Add member
member = pool.members_s.members.create(
    name='192.168.1.10:80',
    partition='Common'
)

# Create virtual server
vs = mgmt.tm.ltm.virtuals.virtual.create(
    name='web_vs',
    partition='Common',
    destination='10.0.1.100:80',
    pool='/Common/web_pool'
)
```

## Best Practices

1. **Version Control** - Store declarations in Git
2. **Validation** - Use AS3 schema validation before deployment
3. **Idempotency** - AS3/DO are idempotent by design
4. **Tenant Isolation** - Use separate tenants per application/team
5. **Testing** - Test declarations in dev/staging first
6. **Backup** - Export declarations before changes

## Common Issues

### AS3 Deployment Fails
```bash
# Check task status
curl -sk -u admin:password \
    https://bigip/mgmt/shared/appsvcs/task

# Get detailed error
curl -sk -u admin:password \
    https://bigip/mgmt/shared/appsvcs/task/<task-id>
```

### Schema Validation
```bash
# Validate against schema locally
npx ajv validate -s as3-schema.json -d declaration.json
```
