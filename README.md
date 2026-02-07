# Mini Housing Search (3-Tier TCP Sockets)

## Files
- data_server.py: Data Server (loads listings.json, answers RAW_LIST / RAW_SEARCH)
- app_server.py: Application Server (client-facing, ranking + caching + logging)
- client.py: Command-line client
- listings.json: dataset (22 entries)
- app_server.log: generated runtime log

## Protocols
Client ↔ App Server:
- LIST
- SEARCH city=<CityName> max_price=<Integer>
- QUIT

App Server ↔ Data Server:
- RAW_LIST
- RAW_SEARCH city=<CityName> max_price=<Integer>

Responses:
- OK RESULT <n>
- <n listing lines>
- END
or
- ERROR <message>