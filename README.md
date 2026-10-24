# ZippyWash Prototype — BTM 495 Team 5

First working prototype of the **ZippyWash Order and Operations Management System**.
It implements the Milestone 3 class diagram as Python classes with real behaviour,
a SQLite database, and a Streamlit interface for customers and staff.

## Run it

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
streamlit run app.py               # opens http://localhost:8501
python -m pytest -q                # 13 business-rule tests
```

The database (`zippywash.db`) is created and filled with demo data on first run.
Delete the file to reset everything.

## What it covers (Prototype 1)

| Use case | What you can do |
|---|---|
| **UC-01 Book Pickup & Delivery** | Pick service, bag size, pickup/delivery address, time slots; confirm the booking |
| **UC-05 Calculate Price & Pay** | Live price breakdown (service, promo, delivery fee, GST, QST); online payment; declined card → retry |
| **UC-02 Track & Update Status** | Customer sees a status timeline + history; drivers and laundry staff advance the status |
| **UC-06 Profile & Order History** | Edit profile, add addresses (sector check), view payment methods, order history, receipts, notifications |

Not in this version: UC-03 machines/inventory, UC-04 routing, UC-07 loyalty
(their tables already exist in the schema for Prototype 2).

## Demo script (2 minutes)

1. **Customer → Léa Tremblay → Book a pickup.** Choose a service, bag size and slots. Type `WELCOME10` and watch the price drop.
2. Pay with **Mastercard ending 0002** → declined (demo card). Retry with **Visa ending 4242** → booked, receipt issued.
3. **My orders** → see the new order as *Scheduled*, plus an older order mid-wash and a delivered one.
4. **Staff → Sofia Haddad (Laundry)** → the "Mark Picked Up" button is disabled: only a Driver can record pickup.
5. **Staff → Marc Gagnon (Driver)** → mark it *Picked Up*. Back as Léa: the timeline moved and a notification arrived; *Cancel* is gone because the bag was picked up.

## How the code maps to the class diagram

```
app.py                              UI only (Streamlit): collects input, shows results
zippywash/
  customer_order_service/           C01 Customer, C02 Address, C03 ServiceType, C04 TimeSlot,
                                    C06 Order, C07 OrderStatusUpdate, C08 Notification,
                                    C11 Payment, C12 PaymentMethod, C14 Promotion
  operations_resource/              C15 Sector, C16 StaffMember
  services/                         BookingService, OrderTrackingService, CustomerProfileService
  integrations/payment_processor.py External Payment Processor actor (mock adapter)
  database/schema.sql               All 23 tables, with the fixes from the repo review
  database/repository.py            Loads/saves domain objects (the DB is not a domain class)
  database/seed.py                  Demo data
  config.py                         Prices, fees and tax rates in one place
tests/test_business_rules.py        Tests for every rule below
```

Each diagram operation is a method on its class, e.g. `Order.calculate_estimate()`,
`Order.confirm()`, `Order.update_status()`, `Order.cancel()`, `TimeSlot.reserve_capacity()`,
`Payment.authorize()`, `Payment.generate_receipt()`, `Payment.refund()`,
`Address.assign_sector()`, `Sector.contains_address()`, `Customer.update_profile()`.
Services only coordinate them.

## Business rules enforced

- An order belongs to one customer and one service type, with a pickup **and** a delivery address and slot.
- Both addresses must belong to the customer and fall inside a service sector.
- Delivery is at least one day after pickup; pickup can't be in the past; full slots can't be booked.
- **Payment is authorized before the order is confirmed.** A declined attempt leaves the order as Draft; each retry is a new Payment record.
- Promotion **xor** Reward (checked in code and by a database constraint). A discount never exceeds the service price.
- Status moves one step at a time through the approved sequence. Drivers record Picked Up / Out for Delivery / Delivered; laundry staff record the washing steps; administrators can record any.
- Every status change is stored as history and sends one notification to exactly one recipient.
- Cancel only while *Scheduled*: frees both slots and refunds the payment.
- Money is stored and calculated as exact decimals, never floats. Card numbers are never stored, only processor tokens.

## Assumptions to confirm with the team

These are placeholders, all in `zippywash/config.py` or `seed.py`:

- Prices: base rate per small bag ($24.99 / $34.99 / $39.99), bag multipliers (×1, ×1.5, ×2), delivery fee $4.99.
- Next-day minimum turnaround; cancellation allowed only before pickup.
- Sectors are defined by postal-code prefixes (Downtown, Plateau).
- All people, addresses and cards are sample data.

## Schema fixes applied (from the team's repo review)

`addresses.customer_id`; explicit `pickup_/delivery_address_id` and `pickup_/delivery_time_slot_id`
(slots nullable only while Draft); `rewards.active`; `route_stops.address_id`; staff links on
`order_status_updates`, `maintenance_records`, `stock_movements`, `supply_orders`;
`staff_members.sector_id`; `loyalty_transactions.reward_id` / `loyalty_rule_id`;
`notifications.status_update_id` / `inventory_item_id`; decimal quantities for inventory.
