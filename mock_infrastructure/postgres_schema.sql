-- Mock PostgreSQL Schema for Adversarial Governance Swarm
-- Represents enterprise auth, cart, and billing database boundaries.

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- User Roles enum
CREATE TYPE user_role AS ENUM ('guest', 'customer', 'support', 'admin', 'super_admin');

-- Users Table
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    role user_role DEFAULT 'customer' NOT NULL,
    is_active BOOLEAN DEFAULT TRUE NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Accounts / Billing profiles
CREATE TABLE billing_profiles (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    payment_method_token VARCHAR(255),
    spending_limit_usd DECIMAL(12, 2) DEFAULT 1000.00 NOT NULL,
    risk_classification VARCHAR(50) DEFAULT 'low' NOT NULL,
    CHECK (spending_limit_usd >= 0.00)
);

-- Products Table
CREATE TABLE products (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) UNIQUE NOT NULL,
    price_usd DECIMAL(12, 2) NOT NULL CHECK (price_usd >= 0.00),
    stock_count INTEGER NOT NULL CHECK (stock_count >= 0)
);

-- Shopping Cart Table
CREATE TABLE carts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    status VARCHAR(50) DEFAULT 'active' NOT NULL CHECK (status IN ('active', 'completed', 'abandoned')),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Cart Items Table
CREATE TABLE cart_items (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cart_id UUID NOT NULL REFERENCES carts(id) ON DELETE CASCADE,
    product_id UUID NOT NULL REFERENCES products(id),
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price_at_addition DECIMAL(12, 2) NOT NULL CHECK (price_at_addition >= 0.00),
    UNIQUE(cart_id, product_id)
);

-- Transaction Audit Logs (Highly critical/immutable)
CREATE TABLE transaction_audit_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    action_type VARCHAR(100) NOT NULL,
    ip_address INET,
    risk_score DECIMAL(5, 2) DEFAULT 0.00 NOT NULL CHECK (risk_score BETWEEN 0.00 AND 100.00),
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP NOT NULL
);

-- Enforce Read-Only Schema Inspection Roles (for MCP access)
-- Note: Agents should only be granted SELECT on these schemas to avoid privilege escalation.
CREATE ROLE swarm_read_only_inspector;
GRANT SELECT ON ALL TABLES IN SCHEMA public TO swarm_read_only_inspector;
