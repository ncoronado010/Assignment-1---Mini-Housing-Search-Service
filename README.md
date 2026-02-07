# Mini Housing Search (3-Tier TCP Sockets)

## Files
- data_server.py: Data Server 
- app_server.py: Application Server
- client.py: Command-line client
- listings.json: dataset
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

## How to Start (Exact Commands, Ports, Order)

### Prerequisites
- Python 3 installed
- Run all commands from the project directory (the folder containing `client.py`, `app_server.py`, `data_server.py`, `listings.json`).

### Default Ports
- Data Server: `127.0.0.1:5001`
- App Server:  `127.0.0.1:5000`

### Start Order (3 Terminals)

#### Terminal 1 — Start Data Server
```bash
python3 data_server.py --host 127.0.0.1 --port 5001 --data listings.json

#### Terminal 2 - Start App Server
python3 app_server.py --host 127.0.0.1 --port 5000 --data-host 127.0.0.1 --data-port 5001

#### Terminal 3 - Start Client
python3 client.py --host 127.0.0.1 --port 5000