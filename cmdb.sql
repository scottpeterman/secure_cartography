-- CMDB Schema Initialization
-- Generated SQL schema for clean database setup

-- Drop existing objects
DROP INDEX IF EXISTS idx_devices_vendor;
DROP INDEX IF EXISTS idx_devices_platform;
DROP INDEX IF EXISTS idx_device_system_info_version;
DROP INDEX IF EXISTS idx_device_serial_numbers_serial;
DROP INDEX IF EXISTS idx_device_mac_table_vlan;
DROP INDEX IF EXISTS idx_device_mac_table_mac;
DROP INDEX IF EXISTS idx_device_mac_table_interface;
DROP INDEX IF EXISTS idx_device_mac_addresses_mac;
DROP INDEX IF EXISTS idx_device_inventory_serial;
DROP INDEX IF EXISTS idx_device_inventory_product;
DROP INDEX IF EXISTS idx_device_inventory_name;
DROP INDEX IF EXISTS idx_device_interfaces_name;
DROP INDEX IF EXISTS idx_device_interfaces_mac;
DROP INDEX IF EXISTS idx_device_interfaces_ip;
DROP INDEX IF EXISTS idx_device_configs_date;
DROP INDEX IF EXISTS idx_device_arp_mac;
DROP INDEX IF EXISTS idx_device_arp_ip;
DROP INDEX IF EXISTS idx_device_arp_interface;
DROP TABLE IF EXISTS devices;
DROP TABLE IF EXISTS device_uptime;
DROP TABLE IF EXISTS device_system_info;
DROP TABLE IF EXISTS device_serial_numbers;
DROP TABLE IF EXISTS device_mac_table;
DROP TABLE IF EXISTS device_mac_addresses;
DROP TABLE IF EXISTS device_inventory;
DROP TABLE IF EXISTS device_interfaces;
DROP TABLE IF EXISTS device_hardware;
DROP TABLE IF EXISTS device_configs;
DROP TABLE IF EXISTS device_arp_table;
DROP VIEW IF EXISTS mac_table_details;
DROP VIEW IF EXISTS mac_addresses_all;
DROP VIEW IF EXISTS ip_addresses_all;
DROP VIEW IF EXISTS inventory_details;
DROP VIEW IF EXISTS interface_details;
DROP VIEW IF EXISTS device_summary;
DROP VIEW IF EXISTS arp_details;

-- Create tables in proper order
CREATE TABLE devices (
        device_id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        ip_address TEXT NOT NULL,
        platform TEXT,
        vendor TEXT,
        model TEXT,
        hostname TEXT,
        detected_prompt TEXT,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(name),
        UNIQUE(ip_address)
    );

CREATE TABLE device_arp_table (
    arp_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    ip_address TEXT NOT NULL,
    mac_address TEXT NOT NULL,
    age TEXT,
    interface TEXT,
    type TEXT,
    vrf TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    UNIQUE(device_id, ip_address, vrf)
);

CREATE TABLE device_configs (
        config_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        config TEXT NOT NULL,
        collected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
    );

CREATE TABLE device_hardware (
        hardware_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        total_memory INTEGER,
        free_memory INTEGER,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
    );

CREATE TABLE device_interfaces (
    interface_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    link_status TEXT,
    protocol_status TEXT,
    interface_type TEXT,
    mac_address TEXT,
    bia TEXT,
    mtu INTEGER,
    bandwidth TEXT,
    duplex TEXT,
    speed TEXT,
    media_type TEXT,
    description TEXT,
    ip_address TEXT,
    input_packets INTEGER,
    output_packets INTEGER,
    input_errors INTEGER,
    output_errors INTEGER,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    UNIQUE(device_id, name)
);

CREATE TABLE device_inventory (
    inventory_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    serial_number TEXT,
    version_id TEXT,
    product_id TEXT,
    port TEXT,
    vendor TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    UNIQUE(device_id, name, serial_number)
);

CREATE TABLE device_mac_addresses (
        mac_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        mac_address TEXT NOT NULL,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
        UNIQUE(device_id, mac_address)
    );

CREATE TABLE device_mac_table (
    mac_table_id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    vlan_id INTEGER,
    mac_address TEXT NOT NULL,
    type TEXT,
    interface TEXT,
    moves INTEGER,
    last_move INTEGER,
    vendor TEXT,
    last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
    UNIQUE(device_id, vlan_id, mac_address, interface)
);

CREATE TABLE device_serial_numbers (
        serial_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        serial_number TEXT NOT NULL,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE,
        UNIQUE(device_id, serial_number)
    );

CREATE TABLE device_system_info (
        system_info_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        software_version TEXT,
        software_image TEXT,
        running_image TEXT,
        rommon_version TEXT,
        boot_reason TEXT,
        config_register TEXT,
        last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
    );

CREATE TABLE device_uptime (
        uptime_id INTEGER PRIMARY KEY AUTOINCREMENT,
        device_id INTEGER NOT NULL,
        years INTEGER DEFAULT 0,
        weeks INTEGER DEFAULT 0,
        days INTEGER DEFAULT 0,
        hours INTEGER DEFAULT 0,
        minutes INTEGER DEFAULT 0,
        recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (device_id) REFERENCES devices(device_id) ON DELETE CASCADE
    );

-- Create view: arp_details
CREATE VIEW arp_details AS
SELECT 
    a.arp_id,
    d.name as device_name,
    d.ip_address as device_ip,
    d.platform,
    a.ip_address as arp_ip,
    a.mac_address,
    a.interface,
    a.age,
    a.type,
    a.vrf,
    dmt.vendor as mac_vendor,
    a.last_updated
FROM device_arp_table a
JOIN devices d ON a.device_id = d.device_id
LEFT JOIN device_mac_table dmt ON a.mac_address = dmt.mac_address 
    AND a.device_id = dmt.device_id;

-- Create view: device_summary
CREATE VIEW device_summary AS
    SELECT 
        d.device_id,
        d.name,
        d.ip_address,
        d.platform,
        d.vendor,
        d.model,
        dsi.software_version,
        dsi.software_image,
        GROUP_CONCAT(DISTINCT dsn.serial_number) as serial_numbers,
        GROUP_CONCAT(DISTINCT dma.mac_address) as mac_addresses,
        du.years as uptime_years,
        du.weeks as uptime_weeks,
        du.days as uptime_days,
        du.hours as uptime_hours,
        du.minutes as uptime_minutes,
        d.last_updated
    FROM devices d
    LEFT JOIN device_system_info dsi ON d.device_id = dsi.device_id
    LEFT JOIN device_serial_numbers dsn ON d.device_id = dsn.device_id
    LEFT JOIN device_mac_addresses dma ON d.device_id = dma.device_id
    LEFT JOIN device_uptime du ON d.device_id = du.device_id
    GROUP BY d.device_id;

-- Create view: interface_details
CREATE VIEW interface_details AS
SELECT 
    i.interface_id,
    d.name as device_name,
    d.ip_address as device_ip,
    d.platform,
    d.vendor,
    i.name as interface_name,
    i.link_status,
    i.protocol_status,
    i.interface_type,
    i.mac_address,
    i.ip_address as interface_ip,
    i.description,
    i.bandwidth,
    i.speed,
    i.duplex,
    i.input_packets,
    i.output_packets,
    i.input_errors,
    i.output_errors,
    i.last_updated
FROM device_interfaces i
JOIN devices d ON i.device_id = d.device_id;

-- Create view: inventory_details
CREATE VIEW inventory_details AS
SELECT 
    i.inventory_id,
    d.name as device_name,
    d.ip_address as device_ip,
    d.platform,
    d.vendor as device_vendor,
    i.name as component_name,
    i.description,
    i.serial_number,
    i.product_id,
    i.version_id,
    i.port,
    i.vendor as component_vendor,
    i.last_updated
FROM device_inventory i
JOIN devices d ON i.device_id = d.device_id;

-- Create view: ip_addresses_all
CREATE VIEW ip_addresses_all AS
SELECT 
    'device' as source_type,
    d.device_id,
    d.name as device_name,
    d.ip_address,
    NULL as interface_name,
    NULL as vrf,
    d.last_updated
FROM devices d
UNION ALL
SELECT 
    'interface' as source_type,
    d.device_id,
    d.name as device_name,
    i.ip_address,
    i.name as interface_name,
    NULL as vrf,
    i.last_updated
FROM device_interfaces i
JOIN devices d ON i.device_id = d.device_id
WHERE i.ip_address IS NOT NULL
UNION ALL
SELECT 
    'arp' as source_type,
    d.device_id,
    d.name as device_name,
    a.ip_address,
    a.interface as interface_name,
    a.vrf,
    a.last_updated
FROM device_arp_table a
JOIN devices d ON a.device_id = d.device_id;

-- Create view: mac_addresses_all
CREATE VIEW mac_addresses_all AS
SELECT 
    'interface' as source_type,
    d.device_id,
    d.name as device_name,
    d.ip_address as device_ip,
    i.name as interface_name,
    i.mac_address,
    NULL as vlan_id,
    NULL as vrf,
    i.last_updated
FROM device_interfaces i
JOIN devices d ON i.device_id = d.device_id
WHERE i.mac_address IS NOT NULL
UNION ALL
SELECT 
    'arp' as source_type,
    d.device_id,
    d.name as device_name,
    d.ip_address as device_ip,
    a.interface as interface_name,
    a.mac_address,
    NULL as vlan_id,
    a.vrf,
    a.last_updated
FROM device_arp_table a
JOIN devices d ON a.device_id = d.device_id
UNION ALL
SELECT 
    'mac_table' as source_type,
    d.device_id,
    d.name as device_name,
    d.ip_address as device_ip,
    mt.interface as interface_name,
    mt.mac_address,
    mt.vlan_id,
    NULL as vrf,
    mt.last_updated
FROM device_mac_table mt
JOIN devices d ON mt.device_id = d.device_id
UNION ALL
SELECT 
    'device_mac' as source_type,
    d.device_id,
    d.name as device_name,
    d.ip_address as device_ip,
    NULL as interface_name,
    dma.mac_address,
    NULL as vlan_id,
    NULL as vrf,
    d.last_updated
FROM device_mac_addresses dma
JOIN devices d ON dma.device_id = d.device_id;

-- Create view: mac_table_details
CREATE VIEW mac_table_details AS
SELECT 
    mt.mac_table_id,
    d.name as device_name,
    d.ip_address as device_ip,
    d.platform,
    d.vendor as device_vendor,
    mt.vlan_id,
    mt.mac_address,
    mt.type,
    mt.interface,
    mt.moves,
    mt.last_move,
    mt.vendor as mac_vendor,
    mt.last_updated
FROM device_mac_table mt
JOIN devices d ON mt.device_id = d.device_id;

-- Create index: idx_device_arp_interface
CREATE INDEX idx_device_arp_interface ON device_arp_table(interface);

-- Create index: idx_device_arp_ip
CREATE INDEX idx_device_arp_ip ON device_arp_table(ip_address);

-- Create index: idx_device_arp_mac
CREATE INDEX idx_device_arp_mac ON device_arp_table(mac_address);

-- Create index: idx_device_configs_date
CREATE INDEX idx_device_configs_date ON device_configs(collected_at);

-- Create index: idx_device_interfaces_ip
CREATE INDEX idx_device_interfaces_ip ON device_interfaces(ip_address);

-- Create index: idx_device_interfaces_mac
CREATE INDEX idx_device_interfaces_mac ON device_interfaces(mac_address);

-- Create index: idx_device_interfaces_name
CREATE INDEX idx_device_interfaces_name ON device_interfaces(name);

-- Create index: idx_device_inventory_name
CREATE INDEX idx_device_inventory_name ON device_inventory(name);

-- Create index: idx_device_inventory_product
CREATE INDEX idx_device_inventory_product ON device_inventory(product_id);

-- Create index: idx_device_inventory_serial
CREATE INDEX idx_device_inventory_serial ON device_inventory(serial_number);

-- Create index: idx_device_mac_addresses_mac
CREATE INDEX idx_device_mac_addresses_mac ON device_mac_addresses(mac_address);

-- Create index: idx_device_mac_table_interface
CREATE INDEX idx_device_mac_table_interface ON device_mac_table(interface);

-- Create index: idx_device_mac_table_mac
CREATE INDEX idx_device_mac_table_mac ON device_mac_table(mac_address);

-- Create index: idx_device_mac_table_vlan
CREATE INDEX idx_device_mac_table_vlan ON device_mac_table(vlan_id);

-- Create index: idx_device_serial_numbers_serial
CREATE INDEX idx_device_serial_numbers_serial ON device_serial_numbers(serial_number);

-- Create index: idx_device_system_info_version
CREATE INDEX idx_device_system_info_version ON device_system_info(software_version);

-- Create index: idx_devices_platform
CREATE INDEX idx_devices_platform ON devices(platform);

-- Create index: idx_devices_vendor
CREATE INDEX idx_devices_vendor ON devices(vendor);

