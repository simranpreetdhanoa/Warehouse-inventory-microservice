# Serverless Warehouse Inventory & Reorder Microservice

Python · AWS Lambda · API Gateway · DynamoDB · SNS · pytest · moto

A serverless API that processes warehouse inventory transactions. Stock is
decremented with atomic DynamoDB conditional updates, so two orders can never
both take the same last unit. When stock falls to or below a dynamically
calculated reorder point, an SNS alert is published.

## Architecture

```
Client ──HTTP──> API Gateway ──> Lambda (inventory.handler)
                                     │
                                     ├── DynamoDB  (atomic UpdateItem with ConditionExpression)
                                     └── SNS topic (REORDER_REQUIRED) ──> email / SQS / other Lambda
```

## Project layout

```
src/inventory/
  handler.py       Lambda entry point: routing, validation, HTTP status codes
  service.py       Orchestration: reserve -> check reorder point -> alert
  repository.py    DynamoDB access (atomic updates)
  safety_stock.py  Pure math: safety stock + reorder point
  notifier.py      SNS publishing
  config.py        Environment variables
tests/
  unit/            No AWS at all (pure logic + handler validation)
  integration/     Full flow against moto's in-memory DynamoDB/SNS/SQS
template.yaml      AWS SAM infrastructure-as-code
events/            Sample API Gateway events for `sam local invoke`
```

## API

| Method | Path                    | Body                    | Result                                   |
|--------|-------------------------|-------------------------|------------------------------------------|
| POST   | `/items`                | item JSON               | 201 created, 409 if SKU exists           |
| GET    | `/items/{sku}`          | none                    | 200 item + reorder point, 404 if missing |
| POST   | `/items/{sku}/reserve`  | `{"quantity": n}`       | 200 decremented, 409 insufficient stock  |
| POST   | `/items/{sku}/restock`  | `{"quantity": n}`       | 200 incremented, reorder flag cleared    |

Item fields: `sku`, `name`, `quantity` (required), plus `avg_daily_demand`,
`demand_std_dev`, `lead_time_days`, `reorder_qty`.

## Dynamic safety stock

```
safety_stock  = ceil(z * demand_std_dev * sqrt(lead_time_days))     z = 1.65 (95% service level)
reorder_point = ceil(avg_daily_demand * lead_time_days) + safety_stock
```

Example: 10/day demand, std dev 4, 9-day lead time gives 90 + 20 = **110**.

## Run the tests locally

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt
pytest -v
```

## Deploy to AWS

Needs the AWS CLI (configured with `aws configure`) and the AWS SAM CLI.

```bash
sam build
sam deploy --guided                # set AlertEmail to receive alerts
```

Then try it (replace `$API` with the ApiUrl output):

```bash
curl -X POST $API/items -d '{"sku":"WID-001","name":"Widget","quantity":150,"avg_daily_demand":10,"demand_std_dev":4,"lead_time_days":9,"reorder_qty":300}'
curl -X POST $API/items/WID-001/reserve -d '{"quantity":45}'
curl $API/items/WID-001
```

Remove everything with `sam delete`.
