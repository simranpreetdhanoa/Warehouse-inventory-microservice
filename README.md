# Warehouse Inventory & Reorder Microservice

A serverless API that keeps track of warehouse stock and **automatically sends an alert when an item needs to be reordered**.

**Built with:** Python · AWS Lambda · API Gateway · DynamoDB · SNS · pytest · moto

---

## What does it do?

1. **Stores products and their stock** (for example, "Widget: 150 units").
2. **Takes orders** and subtracts them from stock.
3. **Never sells more than it has.** If two customers try to buy the last item at the same time, only one succeeds.
4. **Sends a reorder alert** when stock gets too low, so the warehouse never runs out.
5. **Sends only one alert** per low-stock event, not one for every order.

---

## How it works

```
Customer ──► API Gateway ──► Lambda ──► DynamoDB
                               │
                               └──► SNS ──► Email: "Reorder required!"
                                    (only when stock is low)
```

| Part | What it does | Real-world example |
|---|---|---|
| **API Gateway** | Receives requests from the internet | Front desk |
| **Lambda** | Runs the Python code | Clerk |
| **DynamoDB** | Saves the stock numbers | Stock book |
| **SNS** | Sends the low-stock alert | Manager's phone |

---

## Key features

### 1. No over-selling (race condition fix)
If 1 item is left and 2 people order it at the same moment, a simple program could approve both orders, which leaves stock at **-1**.

This project asks DynamoDB to do one **atomic** (unbreakable) step:

> "Subtract 1, **only if** at least 1 is left."

The first order succeeds. The second gets an **"out of stock"** response.

### 2. Smart reorder point
Each product gets its own reorder level based on its sales:

```
Reorder point = (daily sales × delivery days) + safety stock
Example:        (10 × 9) + 20 = 110
```

When stock drops to **110 or below**, an alert is sent.
The **safety stock** is a small extra cushion in case sales are higher than usual.

### 3. No duplicate alerts
After the first alert, a `reorder_pending` flag is set, so later orders don't send more emails.
When new stock arrives (a restock), the flag resets.

---

## API endpoints

| Method | URL | What it does |
|---|---|---|
| `POST` | `/items` | Add a new product |
| `GET` | `/items/{sku}` | See a product's stock |
| `POST` | `/items/{sku}/reserve` | Place an order (removes stock) |
| `POST` | `/items/{sku}/restock` | Add new stock |

**Example order:**
```json
POST /items/WID-001/reserve
{ "quantity": 25 }
```

**Response:**
```json
{ "quantity": 105, "reorder_point": 110, "reorder_triggered": true }
```

---

## Project structure

```
src/inventory/
  handler.py        Receives requests and checks the input
  service.py        Runs the main steps in order
  repository.py     Talks to DynamoDB (atomic updates)
  safety_stock.py   Calculates the reorder point
  notifier.py       Sends the SNS alert
tests/
  unit/             Tests the logic on its own
  integration/      Tests the full flow with a fake AWS
template.yaml       AWS setup (infrastructure as code)
```

---

## Testing

The project has **29 automated tests**.
They use **moto**, a library that runs a **fake AWS on your computer**, so no AWS account is needed.

The tests check that:
- Orders reduce stock correctly
- You can't order more than what's available
- Two customers can't buy the same last item
- An alert is sent when stock gets low
- Only **one** alert is sent, not many
- Bad input (like a negative quantity) is rejected

---

## Run it on your computer

You need **Python 3.11 or newer**.

```bash
# 1. Create a virtual environment
python -m venv .venv

# 2. Activate it
.venv\Scripts\activate          # Windows
source .venv/bin/activate       # Mac / Linux

# 3. Install the libraries
pip install -r requirements-dev.txt

# 4. Run the tests
pytest -v
```

Expected result: **`29 passed`**

---

## Deploy to AWS (optional)

The project includes an **AWS SAM** template, so it can be deployed with two commands
(needs an AWS account plus the AWS CLI and SAM CLI installed):

```bash
sam build
sam deploy --guided
```

---

## What I learned

- Building a **serverless** API with AWS Lambda and API Gateway
- Using **DynamoDB conditional updates** to prevent race conditions
- Sending notifications with **AWS SNS**
- Calculating **safety stock** and **reorder points**
- Testing AWS code **offline** with pytest and moto
- Writing **infrastructure as code** with AWS SAM
