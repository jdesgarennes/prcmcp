# prcmcp

FastMCP server for lab automation. It currently includes a Panorama OpenAPI helper that lets an MCP-capable agent discover Panorama REST API endpoints and make guarded read-only calls with server-side credentials.

## MCP tools

- `ping()` — health check.
- `panorama_config_status()` — confirms whether the server sees Panorama environment variables, without exposing secret values.
- `list_panorama_api_categories()` — lists OpenAPI tags/categories and read-only GET endpoint counts.
- `search_panorama_api(query, method=None, limit=10)` — searches `resources/palo-openapi.json` for matching endpoints.
- `get_panorama_endpoint(path, method="GET")` — returns detailed OpenAPI docs for one endpoint, including parameters.
- `call_panorama_read_api(path, params=None, timeout=30)` — executes a validated read-only GET call against Panorama.

## Safety model

`call_panorama_read_api` is intentionally narrow:

- accepts only OpenAPI paths, not full URLs
- only allows HTTP GET
- only allows paths present in `resources/palo-openapi.json`
- always sends requests to `PANORAMA_BASE_URL`
- uses `PANORAMA_API_KEY` only inside the server process
- does not return the API key in tool output

This is meant for read-only inventory/status/config lookup workflows. Write operations such as POST, PUT, PATCH, DELETE, commits, renames, and deletes are not enabled.

## Runtime secrets

Create the Kubernetes secret in the same namespace as the app:

```bash
kubectl create namespace prcmcp

kubectl create secret generic panorama-credentials \
  --namespace prcmcp \
  --from-literal=PANORAMA_BASE_URL='https://your-panorama-host-or-ip' \
  --from-literal=PANORAMA_API_KEY='your-read-only-api-key' \
  --from-literal=PANORAMA_VERIFY_SSL='false'
```

Use a dedicated read-only Panorama account/API key. Do not commit the API key to GitHub.

The included Kubernetes deployment references this secret as optional so the server can start before credentials are added. The Panorama call tool will return a configuration error until both `PANORAMA_BASE_URL` and `PANORAMA_API_KEY` are set.

## Local development

```bash
pip install -r requirements.txt
pytest -q
fastmcp run app/server.py --transport http --host 0.0.0.0 --port 3000 --path /mcp/
```

Optional local environment for real Panorama reads:

```bash
export PANORAMA_BASE_URL='https://your-panorama-host-or-ip'
export PANORAMA_API_KEY='your-read-only-api-key'
export PANORAMA_VERIFY_SSL='false'
```

## Kubernetes rollout

```bash
kubectl apply -f k8s/prcmcp.yaml
kubectl -n prcmcp rollout restart deploy/prcmcp
```
