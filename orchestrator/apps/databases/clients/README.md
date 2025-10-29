# Database Clients

HTTP clients for interacting with external services.

## InstallationServiceClient

HTTP client for interacting with installation-service (Go microservice).

### Usage

```python
from apps.databases.clients import InstallationServiceClient

# Basic usage
client = InstallationServiceClient()
result = client.get_infobases(
    server='localhost:1545',
    detailed=True
)
print(f"Found {result['total_count']} databases")

# With authentication
client = InstallationServiceClient()
result = client.get_infobases(
    server='localhost:1545',
    cluster_user='admin',
    cluster_pwd='password',
    detailed=True
)

# Context manager
with InstallationServiceClient() as client:
    if client.health_check():
        result = client.get_infobases()
        for ib in result['infobases']:
            print(f"- {ib['name']}: {ib.get('description', 'N/A')}")
```

### Configuration

Set in Django settings or environment variables:

```python
# settings/base.py
INSTALLATION_SERVICE_URL = 'http://localhost:8085'
INSTALLATION_SERVICE_TIMEOUT = 180  # seconds
```

```bash
# .env
INSTALLATION_SERVICE_URL=http://localhost:8085
INSTALLATION_SERVICE_TIMEOUT=180
```

### Response Format

```json
{
  "status": "success",
  "cluster_id": "d2e1f9c8-...",
  "cluster_name": "Local cluster",
  "total_count": 2,
  "infobases": [
    {
      "uuid": "a1b2c3d4-...",
      "name": "accounting_prod",
      "description": "Production accounting database",
      "dbms": "PostgreSQL",
      "db_server": "localhost\\SQLEXPRESS",
      "db_name": "accounting_db",
      "db_user": "dbuser",
      "security_level": 0,
      "connection_string": "...",
      "locale": "ru_RU"
    }
  ],
  "duration_ms": 1250
}
```

### Error Handling

```python
from requests.exceptions import Timeout, ConnectionError, RequestException

try:
    client = InstallationServiceClient()
    result = client.get_infobases()
except Timeout:
    print("Request timed out after 180 seconds")
except ConnectionError:
    print("Cannot connect to installation-service")
except RequestException as e:
    print(f"HTTP error: {e}")
except ValueError as e:
    print(f"Invalid response: {e}")
```

### Methods

#### `health_check() -> bool`

Check if installation-service is available.

**Returns:** `True` if service is available, `False` otherwise

#### `get_infobases(...) -> Dict`

Get list of information bases from 1C cluster.

**Parameters:**
- `server` (str): RAS server address (host:port), default: "localhost:1545"
- `cluster_user` (str, optional): Cluster administrator username
- `cluster_pwd` (str, optional): Cluster administrator password
- `detailed` (bool): Get detailed information, default: False

**Returns:** Dictionary with cluster information and list of infobases

**Raises:**
- `RequestException`: On HTTP errors
- `ValueError`: On invalid response format
- `Timeout`: On request timeout
- `ConnectionError`: On connection errors

### Logging

The client logs all operations at INFO level and errors at ERROR level:

```
INFO: Initialized InstallationServiceClient with base_url=http://localhost:8085
INFO: Calling installation-service: GET /api/v1/infobases with params={'server': 'localhost:1545', 'detailed': 'true'}
INFO: Installation-service response: status=200, duration=1.234s
INFO: Successfully retrieved 2 infobases from cluster 'Local cluster' (d2e1f9c8-...)
```

Passwords are never logged (replaced with `***`).
