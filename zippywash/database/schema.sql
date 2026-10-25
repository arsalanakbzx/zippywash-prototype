-- ZippyWash Order and Operations Management System
-- SQLite schema for the finalized Milestone 3 class diagram (C01-C26, October 26, 2026).
--
-- Notes
--  * C26 Person is abstract and has no table: its attributes (name, contact_details) are stored
--    in customers and staff_members.
--  * Some tables implement multivalued attributes or associations rather than classes:
--    staff_roles (StaffMember.roles [1..*]) and order_item_add_ons (OrderItem.selectedAddOns [0..*]).
--  * Money and decimal quantities are TEXT holding exact decimal strings, read back as Python Decimal,
--    so no floating-point rounding touches a price.
--  * Only payment-processor tokens are stored, never card numbers.

PRAGMA foreign_keys = ON;
PRAGMA user_version = 2;      -- schema version; the app rebuilds an older demo database automatically

-- ======================= Operations & Resource Management =======================

-- C15 Sector
CREATE TABLE IF NOT EXISTS sectors (
    sector_id   TEXT PRIMARY KEY,
    name        TEXT NOT NULL,
    boundary    TEXT NOT NULL,          -- GeoBoundary: comma-separated postal-code prefixes, e.g. "H3H,H3G"
    active      INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C16 StaffMember (a kind of C26 Person)
CREATE TABLE IF NOT EXISTS staff_members (
    staff_member_id TEXT PRIMARY KEY,
    name            TEXT NOT NULL,      -- inherited from Person
    contact_details TEXT NOT NULL,      -- inherited from Person
    sector_id       TEXT REFERENCES sectors(sector_id)       -- only when the Driver role applies
);

-- StaffMember.roles : StaffRole [1..*]  (at least one role is enforced in Python and tested)
CREATE TABLE IF NOT EXISTS staff_roles (
    staff_member_id TEXT NOT NULL REFERENCES staff_members(staff_member_id),
    role            TEXT NOT NULL CHECK (role IN ('LaundryStaff','Driver','Administrator')),
    PRIMARY KEY (staff_member_id, role)
);

-- C25 StaffShift  (StaffMember 1 ◇── 0..* StaffShift)
CREATE TABLE IF NOT EXISTS staff_shifts (
    staff_shift_id  TEXT PRIMARY KEY,
    staff_member_id TEXT NOT NULL REFERENCES staff_members(staff_member_id),
    shift_date      TEXT NOT NULL,
    start_time      TEXT NOT NULL,
    end_time        TEXT NOT NULL,
    status          TEXT NOT NULL CHECK (status IN ('Scheduled','Active','Completed','Cancelled')),
    CHECK (start_time < end_time)
);

-- C24 Vehicle
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id    TEXT PRIMARY KEY,
    slot_capacity INTEGER NOT NULL CHECK (slot_capacity >= 0),
    status        TEXT NOT NULL CHECK (status IN ('Available','InService','Maintenance'))
);

-- ======================= Customer Order & Service Management =======================

-- C01 Customer (a kind of C26 Person)
CREATE TABLE IF NOT EXISTS customers (
    customer_id         TEXT PRIMARY KEY,
    name                TEXT NOT NULL,  -- inherited from Person
    contact_details     TEXT NOT NULL,  -- inherited from Person
    account_status      TEXT NOT NULL DEFAULT 'Active' CHECK (account_status IN ('Active','Deactivated')),
    service_preferences TEXT            -- [0..1]
);

-- C02 Address  (Customer 1 ◇── 0..* Address)
CREATE TABLE IF NOT EXISTS addresses (
    address_id          TEXT PRIMARY KEY,
    customer_id         TEXT NOT NULL REFERENCES customers(customer_id),
    street              TEXT NOT NULL,
    postal_code         TEXT NOT NULL,
    access_instructions TEXT,           -- [0..1]
    serviceable         INTEGER NOT NULL DEFAULT 0 CHECK (serviceable IN (0,1)),
    sector_id           TEXT REFERENCES sectors(sector_id)    -- Sector 0..1 ── 0..* Address
);

-- C03 ServiceType
CREATE TABLE IF NOT EXISTS service_types (
    service_type_id TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    pricing_unit    TEXT NOT NULL DEFAULT 'PerBag' CHECK (pricing_unit IN ('PerBag')),
    base_rate       TEXT NOT NULL,      -- Decimal, price per pricing unit
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C04 TimeSlot
CREATE TABLE IF NOT EXISTS time_slots (
    time_slot_id       TEXT PRIMARY KEY,
    date               TEXT NOT NULL,
    start_time         TEXT NOT NULL,
    available_capacity INTEGER NOT NULL CHECK (available_capacity >= 0)
);

-- C14 Promotion
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id   TEXT PRIMARY KEY,
    code           TEXT NOT NULL UNIQUE,
    discount_value TEXT NOT NULL,
    active         INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    expiry_date    TEXT                 -- [0..1]
);

-- C13 Reward
CREATE TABLE IF NOT EXISTS rewards (
    reward_id       TEXT PRIMARY KEY,
    name            TEXT NOT NULL,
    points_required INTEGER NOT NULL CHECK (points_required > 0),
    discount_amount TEXT NOT NULL,
    active          INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1)),
    expiry_date     TEXT                -- [0..1]
);

-- C06 Order
CREATE TABLE IF NOT EXISTS orders (
    order_id              TEXT PRIMARY KEY,
    customer_id           TEXT NOT NULL REFERENCES customers(customer_id),
    bag_size              TEXT NOT NULL CHECK (bag_size IN ('Small','Medium','Large')),
    status                TEXT NOT NULL CHECK (status IN ('Draft','Scheduled','Picked Up','Waiting for Wash',
                               'Washing','Ready for Pickup','Out for Delivery','Delivered','Cancelled')),
    pickup_request_type   TEXT NOT NULL DEFAULT 'Scheduled' CHECK (pickup_request_type IN ('Scheduled','Live')),
    subtotal              TEXT NOT NULL,
    delivery_fee          TEXT NOT NULL,
    tax_amount            TEXT NOT NULL,
    discount_amount       TEXT NOT NULL,
    estimated_total       TEXT NOT NULL,
    final_total           TEXT,         -- [0..1], set when payment is authorized
    pickup_address_id     TEXT NOT NULL REFERENCES addresses(address_id),
    delivery_address_id   TEXT NOT NULL REFERENCES addresses(address_id),
    pickup_time_slot_id   TEXT REFERENCES time_slots(time_slot_id),     -- nullable only while Draft
    delivery_time_slot_id TEXT REFERENCES time_slots(time_slot_id),
    promotion_id          TEXT REFERENCES promotions(promotion_id),
    reward_id             TEXT REFERENCES rewards(reward_id),
    created_at            TEXT NOT NULL,
    CHECK (promotion_id IS NULL OR reward_id IS NULL),                   -- {xor} Promotion / Reward
    CHECK (status = 'Draft' OR (pickup_time_slot_id IS NOT NULL AND delivery_time_slot_id IS NOT NULL))
);

-- C23 OrderItem  (Order 1 ◇── 1..* OrderItem;  OrderItem * ── 1 ServiceType)
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id   TEXT PRIMARY KEY,
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    service_type_id TEXT NOT NULL REFERENCES service_types(service_type_id),
    quantity        TEXT NOT NULL,
    unit_price      TEXT NOT NULL,
    line_total      TEXT NOT NULL
);

-- OrderItem.selectedAddOns : AddOnType [0..*]  (multivalued attribute -> junction table)
CREATE TABLE IF NOT EXISTS order_item_add_ons (
    order_item_id TEXT NOT NULL REFERENCES order_items(order_item_id),
    add_on        TEXT NOT NULL CHECK (add_on IN ('StainTreatment','FabricSoftener',
                                                  'HypoallergenicDetergent','HangDry')),
    PRIMARY KEY (order_item_id, add_on)
);

-- C07 OrderStatusUpdate  (Order 1 ◇── 1..* OrderStatusUpdate)
CREATE TABLE IF NOT EXISTS order_status_updates (
    status_update_id     TEXT PRIMARY KEY,
    order_id             TEXT NOT NULL REFERENCES orders(order_id),
    status               TEXT NOT NULL,
    changed_at           TEXT NOT NULL,
    notes                TEXT,                                          -- [0..1]
    recorded_by_staff_id TEXT REFERENCES staff_members(staff_member_id) -- 0..1: automatic updates have none
);

-- C12 PaymentMethod
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id TEXT PRIMARY KEY,
    customer_id       TEXT NOT NULL REFERENCES customers(customer_id),
    token             TEXT NOT NULL,    -- processor token only; card numbers are never stored
    type              TEXT NOT NULL CHECK (type IN ('CreditCard','DebitCard','DigitalWallet')),
    label             TEXT NOT NULL,    -- display text for the UI (not a Milestone 3 attribute)
    active            INTEGER NOT NULL DEFAULT 1 CHECK (active IN (0,1))
);

-- C11 Payment  (Order 1 ── 0..* payment attempts)
CREATE TABLE IF NOT EXISTS payments (
    payment_id        TEXT PRIMARY KEY,
    order_id          TEXT NOT NULL REFERENCES orders(order_id),
    payment_method_id TEXT NOT NULL REFERENCES payment_methods(payment_method_id),
    amount            TEXT NOT NULL,
    status            TEXT NOT NULL CHECK (status IN ('Pending','Authorized','Declined','Refunded')),
    receipt_number    TEXT,             -- [0..1], only on success
    created_at        TEXT NOT NULL
);

-- C05 LoyaltyAccount  (Customer 1 ◇── 0..1 LoyaltyAccount)
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

-- C10 LoyaltyTransaction  (LoyaltyAccount 1 ◇── 0..* LoyaltyTransaction; other links depend on the type)
CREATE TABLE IF NOT EXISTS loyalty_transactions (
    transaction_id         TEXT PRIMARY KEY,
    loyalty_account_id     TEXT NOT NULL REFERENCES loyalty_accounts(loyalty_account_id),
    type                   TEXT NOT NULL CHECK (type IN ('Earn','Reserve','Redeem','Restore','Adjustment','Reversal')),
    points                 INTEGER NOT NULL,
    reason                 TEXT,        -- [0..1]; required for an Administrator adjustment
    created_at             TEXT NOT NULL,
    order_id               TEXT REFERENCES orders(order_id),
    payment_id             TEXT REFERENCES payments(payment_id),
    reward_id              TEXT REFERENCES rewards(reward_id),
    loyalty_rule_id        TEXT REFERENCES loyalty_rules(loyalty_rule_id),
    authorized_by_staff_id TEXT REFERENCES staff_members(staff_member_id),
    CHECK (type <> 'Adjustment' OR (reason IS NOT NULL AND authorized_by_staff_id IS NOT NULL))
);

-- C19 Machine
CREATE TABLE IF NOT EXISTS machines (
    machine_id    TEXT PRIMARY KEY,
    type          TEXT NOT NULL CHECK (type IN ('Washer','Dryer')),
    status        TEXT NOT NULL CHECK (status IN ('Operational','Faulty','UnderMaintenance','OutOfService')),
    capacity      TEXT NOT NULL,
    current_cycle TEXT                  -- [0..1]
);

-- C20 MaintenanceRecord  (Machine 1 ◇── 0..* MaintenanceRecord)
CREATE TABLE IF NOT EXISTS maintenance_records (
    maintenance_record_id TEXT PRIMARY KEY,
    machine_id            TEXT NOT NULL REFERENCES machines(machine_id),
    fault_description     TEXT NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('Reported','Scheduled','InRepair','Completed')),
    scheduled_date        TEXT,         -- [0..1]
    managed_by_staff_id   TEXT REFERENCES staff_members(staff_member_id)
);

-- C21 InventoryItem
CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_item_id TEXT PRIMARY KEY,
    name              TEXT NOT NULL,
    quantity_on_hand  TEXT NOT NULL,    -- Decimal (e.g. litres of detergent)
    reorder_level     TEXT NOT NULL
);

-- C22 StockMovement  (InventoryItem 1 ◇── 0..* StockMovement)
CREATE TABLE IF NOT EXISTS stock_movements (
    stock_movement_id    TEXT PRIMARY KEY,
    inventory_item_id    TEXT NOT NULL REFERENCES inventory_items(inventory_item_id),
    type                 TEXT NOT NULL CHECK (type IN ('Consumption','Receipt','Adjustment')),
    quantity             TEXT NOT NULL,
    recorded_at          TEXT NOT NULL,
    recorded_by_staff_id TEXT REFERENCES staff_members(staff_member_id)
);

-- C08 Notification  ({xor} recipient: Customer or StaffMember; optional link to what generated it)
CREATE TABLE IF NOT EXISTS notifications (
    notification_id   TEXT PRIMARY KEY,
    type              TEXT NOT NULL CHECK (type IN ('BookingConfirmed','StatusChanged','PaymentResult',
                                                    'LowStock','RouteAssigned','MachineFault')),
    message           TEXT NOT NULL,
    delivery_status   TEXT NOT NULL DEFAULT 'Pending' CHECK (delivery_status IN ('Pending','Sent','Delivered','Failed')),
    customer_id       TEXT REFERENCES customers(customer_id),
    staff_member_id   TEXT REFERENCES staff_members(staff_member_id),
    status_update_id  TEXT REFERENCES order_status_updates(status_update_id),
    payment_id        TEXT REFERENCES payments(payment_id),
    machine_id        TEXT REFERENCES machines(machine_id),
    inventory_item_id TEXT REFERENCES inventory_items(inventory_item_id),
    created_at        TEXT NOT NULL,
    CHECK ((customer_id IS NULL) <> (staff_member_id IS NULL))            -- exactly one recipient
);

-- C17 Route  (driver reached through StaffShift: StaffMember -> StaffShift -> Route)
CREATE TABLE IF NOT EXISTS routes (
    route_id       TEXT PRIMARY KEY,
    sector_id      TEXT NOT NULL REFERENCES sectors(sector_id),
    vehicle_id     TEXT NOT NULL REFERENCES vehicles(vehicle_id),
    staff_shift_id TEXT NOT NULL UNIQUE REFERENCES staff_shifts(staff_shift_id),   -- a shift has 0..1 route
    route_date     TEXT NOT NULL,
    status         TEXT NOT NULL CHECK (status IN ('Draft','Optimized','Finalized','InProgress','Completed')),
    total_distance TEXT NOT NULL DEFAULT '0',
    occupied_slots INTEGER NOT NULL DEFAULT 0 CHECK (occupied_slots >= 0)
);

-- C18 RouteStop  (Route 1 ◇── 1..* RouteStop; Order 1 ── 0..2 RouteStop)
CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id   TEXT PRIMARY KEY,
    route_id        TEXT NOT NULL REFERENCES routes(route_id),
    order_id        TEXT NOT NULL REFERENCES orders(order_id),
    address_id      TEXT NOT NULL REFERENCES addresses(address_id),
    sequence_number INTEGER NOT NULL CHECK (sequence_number >= 1),
    stop_type       TEXT NOT NULL CHECK (stop_type IN ('Pickup','Delivery')),
    status          TEXT NOT NULL CHECK (status IN ('Planned','Completed','Skipped'))
);
