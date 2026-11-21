-- ZippyWash Prototype 2 schema (generated from zippywash/database/mapping.py).
-- Money and quantities are stored as exact decimal TEXT, never as binary floats.
PRAGMA user_version = 3;

CREATE TABLE IF NOT EXISTS sectors (
    sector_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    boundary TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contact_details TEXT NOT NULL,
    account_status TEXT NOT NULL,
    service_preferences TEXT
);
CREATE TABLE IF NOT EXISTS staff_members (
    staff_member_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contact_details TEXT NOT NULL,
    roles TEXT NOT NULL,
    assigned_sector_id TEXT REFERENCES sectors(sector_id)
);
CREATE TABLE IF NOT EXISTS addresses (
    address_id TEXT PRIMARY KEY,
    street TEXT NOT NULL,
    postal_code TEXT NOT NULL,
    access_instructions TEXT,
    serviceable INTEGER NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    sector_id TEXT REFERENCES sectors(sector_id)
);
CREATE TABLE IF NOT EXISTS service_types (
    service_type_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    pricing_unit TEXT NOT NULL,
    base_rate TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS machines (
    machine_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    status TEXT NOT NULL,
    capacity TEXT NOT NULL,
    current_cycle TEXT
);
CREATE TABLE IF NOT EXISTS time_slots (
    time_slot_id TEXT PRIMARY KEY,
    date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    available_capacity INTEGER NOT NULL,
    capacity_limit INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS promotions (
    promotion_id TEXT PRIMARY KEY,
    code TEXT NOT NULL,
    discount_value TEXT NOT NULL,
    active INTEGER NOT NULL,
    expiry_date TEXT
);
CREATE TABLE IF NOT EXISTS rewards (
    reward_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    points_required INTEGER NOT NULL,
    discount_amount TEXT NOT NULL,
    active INTEGER NOT NULL,
    available_from TEXT,
    expiry_date TEXT
);
CREATE TABLE IF NOT EXISTS loyalty_rules (
    loyalty_rule_id TEXT PRIMARY KEY,
    points_per_dollar TEXT NOT NULL,
    effective_from TEXT NOT NULL,
    active INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS loyalty_accounts (
    loyalty_account_id TEXT PRIMARY KEY,
    point_balance INTEGER NOT NULL,
    status TEXT NOT NULL,
    enrolled_date TEXT,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id)
);
CREATE TABLE IF NOT EXISTS payment_methods (
    payment_method_id TEXT PRIMARY KEY,
    token TEXT NOT NULL,
    type TEXT NOT NULL,
    active INTEGER NOT NULL,
    label TEXT NOT NULL,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id)
);
CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    bag_size TEXT NOT NULL,
    status TEXT NOT NULL,
    pickup_request_type TEXT NOT NULL,
    subtotal TEXT NOT NULL,
    delivery_fee TEXT NOT NULL,
    tax_amount TEXT NOT NULL,
    discount_amount TEXT NOT NULL,
    estimated_total TEXT NOT NULL,
    final_total TEXT,
    dispute_status TEXT,
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    pickup_address_id TEXT NOT NULL REFERENCES addresses(address_id),
    delivery_address_id TEXT NOT NULL REFERENCES addresses(address_id),
    service_type_id TEXT NOT NULL REFERENCES service_types(service_type_id),
    pickup_time_slot_id TEXT REFERENCES time_slots(time_slot_id),
    delivery_time_slot_id TEXT REFERENCES time_slots(time_slot_id),
    applied_promotion_id TEXT REFERENCES promotions(promotion_id),
    applied_reward_id TEXT REFERENCES rewards(reward_id)
);
CREATE TABLE IF NOT EXISTS order_items (
    order_item_id TEXT PRIMARY KEY,
    quantity INTEGER NOT NULL,
    unit_price TEXT NOT NULL,
    line_total TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id)
);
CREATE TABLE IF NOT EXISTS order_status_updates (
    status_update_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    changed_at TEXT NOT NULL,
    notes TEXT,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    recorded_by_id TEXT REFERENCES staff_members(staff_member_id)
);
CREATE TABLE IF NOT EXISTS payments (
    payment_id TEXT PRIMARY KEY,
    amount TEXT NOT NULL,
    status TEXT NOT NULL,
    receipt_number TEXT,
    created_at TEXT,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    payment_method_id TEXT NOT NULL REFERENCES payment_methods(payment_method_id)
);
CREATE TABLE IF NOT EXISTS loyalty_transactions (
    transaction_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    points INTEGER NOT NULL,
    reason TEXT,
    created_at TEXT NOT NULL,
    posted INTEGER NOT NULL,
    loyalty_account_id TEXT NOT NULL REFERENCES loyalty_accounts(loyalty_account_id),
    order_id TEXT REFERENCES orders(order_id),
    reward_id TEXT REFERENCES rewards(reward_id),
    applied_rule_id TEXT REFERENCES loyalty_rules(loyalty_rule_id),
    payment_id TEXT REFERENCES payments(payment_id),
    authorized_by_id TEXT REFERENCES staff_members(staff_member_id),
    reservation_id TEXT REFERENCES loyalty_transactions(transaction_id),
    reverses_id TEXT REFERENCES loyalty_transactions(transaction_id)
);
CREATE TABLE IF NOT EXISTS vehicles (
    vehicle_id TEXT PRIMARY KEY,
    slot_capacity INTEGER NOT NULL,
    status TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS staff_shifts (
    staff_shift_id TEXT PRIMARY KEY,
    shift_date TEXT NOT NULL,
    start_time TEXT NOT NULL,
    end_time TEXT NOT NULL,
    status TEXT NOT NULL,
    staff_member_id TEXT NOT NULL REFERENCES staff_members(staff_member_id)
);
CREATE TABLE IF NOT EXISTS routes (
    route_id TEXT PRIMARY KEY,
    route_date TEXT NOT NULL,
    status TEXT NOT NULL,
    total_distance TEXT NOT NULL,
    occupied_slots INTEGER NOT NULL,
    sector_id TEXT REFERENCES sectors(sector_id),
    vehicle_id TEXT REFERENCES vehicles(vehicle_id),
    staff_shift_id TEXT REFERENCES staff_shifts(staff_shift_id)
);
CREATE TABLE IF NOT EXISTS route_stops (
    route_stop_id TEXT PRIMARY KEY,
    sequence_number INTEGER NOT NULL,
    stop_type TEXT NOT NULL,
    status TEXT NOT NULL,
    estimated_arrival_time TEXT,
    route_id TEXT NOT NULL REFERENCES routes(route_id),
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    address_id TEXT NOT NULL REFERENCES addresses(address_id)
);
CREATE TABLE IF NOT EXISTS maintenance_records (
    maintenance_record_id TEXT PRIMARY KEY,
    fault_description TEXT NOT NULL,
    repair_details TEXT,
    status TEXT NOT NULL,
    scheduled_date TEXT,
    machine_id TEXT NOT NULL REFERENCES machines(machine_id),
    managed_by_id TEXT REFERENCES staff_members(staff_member_id)
);
CREATE TABLE IF NOT EXISTS inventory_items (
    inventory_item_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    quantity_on_hand TEXT NOT NULL,
    reorder_level TEXT NOT NULL,
    alert_open INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS stock_movements (
    stock_movement_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    quantity TEXT NOT NULL,
    recorded_at TEXT NOT NULL,
    inventory_item_id TEXT NOT NULL REFERENCES inventory_items(inventory_item_id),
    recorded_by_id TEXT REFERENCES staff_members(staff_member_id)
);
CREATE TABLE IF NOT EXISTS notifications (
    notification_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    message TEXT NOT NULL,
    delivery_status TEXT NOT NULL,
    created_at TEXT,
    customer_recipient_id TEXT REFERENCES customers(customer_id),
    staff_recipient_id TEXT REFERENCES staff_members(staff_member_id),
    status_update_id TEXT REFERENCES order_status_updates(status_update_id),
    payment_id TEXT REFERENCES payments(payment_id),
    machine_id TEXT REFERENCES machines(machine_id),
    inventory_item_id TEXT REFERENCES inventory_items(inventory_item_id)
);
CREATE TABLE IF NOT EXISTS time_slot_machines (
    time_slot_id TEXT NOT NULL REFERENCES time_slots(time_slot_id),
    machine_id TEXT NOT NULL REFERENCES machines(machine_id),
    PRIMARY KEY (time_slot_id, machine_id)
);
