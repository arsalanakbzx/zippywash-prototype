-- ZippyWash Order and Operations Management System
-- SQLite schema derived from the Milestone 3 class diagram (23 classes, C01-C23).
-- Money and decimal quantities are stored as TEXT holding exact decimal strings
-- (read back into Python Decimal) so no floating-point rounding ever touches a price.
-- Fixes applied from the team's GitHub review notes are marked "FIX:".

PRAGMA foreign_keys = ON;

-- ============ Operations & Resource Management (referenced by customer side) ============

-- C15 Sector
CREATE TABLE IF NOT EXISTS sectors (
    sector_id      TEXT PRIMARY KEY,
    name           TEXT NOT NULL,
    boundary       TEXT NOT NULL,              -- GeoBoundary: comma-separated postal-code prefixes (FSA), e.g. "H3H,H3G"
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C16 StaffMember
CREATE TABLE IF NOT EXISTS staff_members (
    staff_member_id TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    availability    TEXT NOT NULL DEFAULT 'Available'
                    CHECK (availability IN ('Available','Busy','Off')),
    sector_id       TEXT REFERENCES sectors(sector_id)        -- FIX: Sector 0..1 -- 0..* StaffMember
);

-- StaffMember.roles : StaffRole [1..*]  (multi-valued attribute -> junction table)
CREATE TABLE IF NOT EXISTS staff_roles (
    staff_member_id TEXT NOT NULL REFERENCES staff_members(staff_member_id),
    role            TEXT NOT NULL CHECK (role IN ('LaundryStaff','Driver','Administrator')),
    PRIMARY KEY (staff_member_id, role)
);

-- ============ Customer Order & Service Management ============

-- C01 Customer
CREATE TABLE IF NOT EXISTS customers (
    customer_id     TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    contact_details TEXT NOT NULL,
    account_status  TEXT NOT NULL DEFAULT 'Active'
                    CHECK (account_status IN ('Active','Deactivated'))
);

-- C02 Address  (aggregated by Customer 1 -- 0..*)
CREATE TABLE IF NOT EXISTS addresses (
    address_id   TEXT PRIMARY KEY,
    customer_id  TEXT NOT NULL REFERENCES customers(customer_id),   -- FIX: address now knows its owner
    street       TEXT NOT NULL,
    postal_code  TEXT NOT NULL,
    serviceable  INTEGER NOT NULL DEFAULT 0 CHECK (serviceable IN (0,1)),
    sector_id    TEXT REFERENCES sectors(sector_id)                 -- Sector 0..1 -- 0..* Address
);

-- C03 ServiceType
CREATE TABLE IF NOT EXISTS service_types (
    service_type_id TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    base_rate       TEXT NOT NULL,             -- Decimal, price per standard bag
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C04 TimeSlot
CREATE TABLE IF NOT EXISTS time_slots (
    time_slot_id       TEXT PRIMARY KEY,
    date               TEXT NOT NULL,          -- ISO date
    start_time         TEXT NOT NULL,          -- HH:MM
    available_capacity INTEGER NOT NULL CHECK (available_capacity >= 0)
);

-- C14 Promotion
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id   TEXT PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    discount_value TEXT NOT NULL,              -- Decimal, fixed dollar amount off
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C13 Reward
CREATE TABLE IF NOT EXISTS rewards (
    reward_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    points_required INTEGER NOT NULL CHECK (points_required > 0),
    discount_amount TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))   -- FIX: needed by activate()/deactivate()
);

-- C06 Order
CREATE TABLE IF NOT EXISTS orders (
    order_id              TEXT PRIMARY KEY,
    customer_id           TEXT NOT NULL REFERENCES customers(customer_id),
    service_type_id       TEXT NOT NULL REFERENCES service_types(service_type_id),
    bag_size              TEXT NOT NULL CHECK (bag_size IN ('Small','Medium','Large')),
    status                TEXT NOT NULL CHECK (status IN ('Draft','Scheduled','Picked Up','Waiting for Wash',
                                   'Washing','Ready for Pickup','Out for Delivery','Delivered','Cancelled')),
    estimated_total       TEXT NOT NULL,
    -- FIX: explicit address and time-slot roles instead of one combined 1..2 / 0..2 association
    pickup_address_id     TEXT NOT NULL REFERENCES addresses(address_id),
    delivery_address_id   TEXT NOT NULL REFERENCES addresses(address_id),
    pickup_time_slot_id   TEXT REFERENCES time_slots(time_slot_id),     -- FIX: nullable while Draft (0..2)
    delivery_time_slot_id TEXT REFERENCES time_slots(time_slot_id),
    promotion_id          TEXT REFERENCES promotions(promotion_id),
    reward_id             TEXT REFERENCES rewards(reward_id),
    created_at            TEXT NOT NULL,
    CHECK (promotion_id IS NULL OR reward_id IS NULL),                   -- {xor} Promotion / Reward
    CHECK (status = 'Draft' OR (pickup_time_slot_id IS NOT NULL AND delivery_time_slot_id IS NOT NULL))
);

-- C07 OrderStatusUpdate  (aggregated by Order 1 -- 1..*)
CREATE TABLE IF NOT EXISTS order_status_updates (
    status_update_id      TEXT PRIMARY KEY,
    order_id              TEXT NOT NULL REFERENCES orders(order_id),
    status                TEXT NOT NULL,
    changed_at            TEXT NOT NULL,
    notes                 TEXT,
    recorded_by_staff_id  TEXT REFERENCES staff_members(staff_member_id)  -- FIX: StaffMember 0..1 recorded by
);

-- C12 PaymentMethod
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL REFERENCES customers(customer_id),
    token             TEXT NOT NULL,           -- processor token only; card numbers are never stored
    type              TEXT NOT NULL CHECK (type IN ('CreditCard','DebitCard','DigitalWallet')),
    label             TEXT NOT NULL,           -- display text, e.g. "Visa ending 4242"
    active            INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C11 Payment  (Order 1 -- 0..* payment attempts)
CREATE TABLE IF NOT EXISTS payments (
    payment_id        TEXT PRIMARY KEY,
    order_id          TEXT NOT NULL REFERENCES orders(order_id),
    payment_method_id TEXT NOT NULL REFERENCES payment_methods(payment_method_id),
    amount            TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('Pending','Authorized','Declined','Refunded')),
    receipt_number    TEXT,                    -- [0..1], only on success
    created_at        TEXT NOT NULL
);

-- C05 LoyaltyAccount  (Customer 1 -- 0..1)
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    loyalty_account_id TEXT PRIMARY KEY,
    customer_id        TEXT NOT NULL UNIQUE REFERENCES customers(customer_id),
    point_balance      INTEGER NOT NULL DEFAULT 0 CHECK (point_balance >= 0),
    status             TEXT NOT NULL DEFAULT 'Active' CHECK (status IN ('Active','Inactive')),
    enrolled_date      TEXT NOT NULL
);

-- C09 LoyaltyRule
CREATE TABLE IF NOT EXISTS loyalty_rules (
    loyalty_rule_id   TEXT PRIMARY KEY,
    points_per_dollar TEXT NOT NULL,
    effective_from    TEXT NOT NULL,
    active            INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C10 LoyaltyTransaction
CREATE TABLE IF NOT EXISTS loyalty_transactions (
    transaction_id     TEXT PRIMARY KEY,
    loyalty_account_id TEXT NOT NULL REFERENCES loyalty_accounts(loyalty_account_id),
    type               TEXT NOT NULL CHECK (type IN ('Earn','Reserve','Redeem','Restore','Adjustment','Reversal')),
    points             INTEGER NOT NULL,
    created_at         TEXT NOT NULL,
    order_id           TEXT REFERENCES orders(order_id),
    reward_id          TEXT REFERENCES rewards(reward_id),               -- FIX
    loyalty_rule_id    TEXT REFERENCES loyalty_rules(loyalty_rule_id),   -- FIX
    reason             TEXT                                              -- required for admin Adjustment (audit)
);

-- C21 InventoryItem (declared before notifications, which can reference it)
CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_item_id TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    quantity_on_hand  TEXT NOT NULL,           -- FIX: Decimal, not INTEGER (detergent in litres)
    reorder_level     TEXT NOT NULL
);

-- C08 Notification  ({xor} recipient: Customer or StaffMember)
CREATE TABLE IF NOT EXISTS notifications (
    notification_id    TEXT PRIMARY KEY,
    type               TEXT NOT NULL CHECK (type IN ('BookingConfirmed','StatusChanged','PaymentResult','LowStock','RouteAssigned')),
    message            TEXT NOT NULL,
    delivery_status    TEXT NOT NULL DEFAULT 'Pending' CHECK (delivery_status IN ('Pending','Sent','Delivered','Failed')),
    customer_id        TEXT REFERENCES customers(customer_id),
    staff_member_id    TEXT REFERENCES staff_members(staff_member_id),
    status_update_id   TEXT REFERENCES order_status_updates(status_update_id),  -- FIX
    inventory_item_id  TEXT REFERENCES inventory_items(inventory_item_id),       -- FIX: low-stock alert
    created_at         TEXT NOT NULL,
    CHECK ((customer_id IS NULL) <> (staff_member_id IS NULL))                   -- exactly one recipient
);

-- C17 Route
CREATE TABLE IF NOT EXISTS routes (
    route_id        TEXT PRIMARY KEY,
    sector_id       TEXT NOT NULL REFERENCES sectors(sector_id),
    staff_member_id TEXT NOT NULL REFERENCES staff_members(staff_member_id),
    route_date      TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('Draft','Optimized','Finalized','InProgress','Completed')),
    total_distance  TEXT NOT NULL DEFAULT '0'
);

-- C18 RouteStop
CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id   TEXT PRIMARY KEY,
    route_id        TEXT NOT NULL REFERENCES routes(route_id),
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    address_id      TEXT NOT NULL REFERENCES addresses(address_id),   -- FIX: every stop has an address
    sequence_number INTEGER NOT NULL,
    stop_type       TEXT NOT NULL CHECK (stop_type IN ('Pickup','Delivery')),
    status          TEXT NOT NULL CHECK (status IN ('Planned','Completed','Skipped'))
);

-- C19 Machine
CREATE TABLE IF NOT EXISTS machines (
    machine_id TEXT PRIMARY KEY,
    type       TEXT NOT NULL CHECK (type IN ('Washer','Dryer')),
    status     TEXT NOT NULL CHECK (status IN ('Operational','Faulty','UnderMaintenance','OutOfService')),
    capacity   TEXT NOT NULL
);

-- C20 MaintenanceRecord
CREATE TABLE IF NOT EXISTS maintenance_records (
    maintenance_record_id TEXT PRIMARY KEY,
    machine_id            TEXT NOT NULL REFERENCES machines(machine_id),
    fault_description     TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('Reported','Scheduled','InRepair','Completed')),
    scheduled_date        TEXT,
    managed_by_staff_id   TEXT REFERENCES staff_members(staff_member_id)   -- FIX
);

-- C22 StockMovement
CREATE TABLE IF NOT EXISTS stock_movements (
    stock_movement_id    TEXT PRIMARY KEY,
    inventory_item_id    TEXT NOT NULL REFERENCES inventory_items(inventory_item_id),
    type                 TEXT NOT NULL CHECK (type IN ('Consumption','Receipt','Adjustment')),
    quantity             TEXT NOT NULL,         -- FIX: Decimal
    recorded_at          TEXT NOT NULL,
    recorded_by_staff_id TEXT NOT NULL REFERENCES staff_members(staff_member_id)   -- FIX
);

-- C23 SupplyOrder
CREATE TABLE IF NOT EXISTS supply_orders (
    supply_order_id        TEXT PRIMARY KEY,
    inventory_item_id      TEXT NOT NULL REFERENCES inventory_items(inventory_item_id),
    quantity_ordered       TEXT NOT NULL,       -- FIX: Decimal
    status                 TEXT NOT NULL CHECK (status IN ('Placed','Confirmed','Received','Cancelled')),
    expected_delivery_date TEXT,
    placed_by_staff_id     TEXT NOT NULL REFERENCES staff_members(staff_member_id)   -- FIX
);
