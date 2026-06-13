# Supabase Setup Guide for Request Auditing & Access Control

To successfully log requests and manage bot access control via the database, you need to create the required tables in your Supabase project and configure the environment variables on Vercel and locally.

---

## 1. Create or Reset the Audit Table in Supabase

Since PostgreSQL does not support reorganizing columns on an existing table directly, the easiest way to apply the new column order and add the default role tracker is to **drop and recreate the table**.

Run the following SQL script in your Supabase **SQL Editor**:

```sql
-- Drop the existing table to reset the column order
drop table if exists request_audit;

-- Create request_audit table with updated column order and role tracker
create table request_audit (
  id bigint generated always as identity primary key,
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  endpoint text not null,                -- 'webhook', 'fact_scheduler', 'news_scheduler'
  status text not null,                  -- 'success', 'error', 'access_denied', etc.
  inserted_by text default current_user, -- Automatically logs database role used ('service_role', 'anon', 'postgres')
  user_id bigint,                        -- Telegram user ID (if webhook)
  username text,                         -- Telegram username (if webhook)
  chat_id bigint,                        -- Telegram chat ID (if applicable)
  command text,                          -- Command query or arguments executed
  topic text,                            -- The generated fact seed topic or search query keyword
  response_content text,                 -- The message body sent back to the Telegram user
  execution_time_ms integer,             -- Duration of request execution in milliseconds
  error_message text                     -- Error details if status is 'error'
);

-- Enable index for fast querying by endpoint/created_at
create index idx_request_audit_endpoint_created_at 
on request_audit (endpoint, created_at desc);
```

> [!NOTE]
> Since we omitted `inserted_by` from the Python insertion payload, PostgreSQL will automatically populate it with the name of the role that made the connection (e.g., `service_role` or `anon`).

---

## 2. Create the Allowed Users Table (Access Control)

You can manage which Telegram users have access to use the bot dynamically via database records, without redeploying Vercel code or modifying environment variables.

### Clean Setup SQL
Run this SQL script in your Supabase **SQL Editor** if creating the table for the first time:

```sql
-- Create allowed_users table
create table allowed_users (
  user_id bigint primary key,            -- Telegram User ID
  username text,                         -- Telegram username (for reference)
  role text default 'regular' check (role in ('admin', 'regular')), -- User role (admin or regular)
  is_active boolean default true not null, -- Active status (true = allowed, false = revoked)
  created_at timestamp with time zone default timezone('utc'::text, now()) not null,
  added_by text default current_user
);

-- Example: Add yourself as an admin (replace with your Telegram User ID)
insert into allowed_users (user_id, username, role, is_active) 
values (973133568, 'your_telegram_username', 'admin', true);
```

### Migration SQL (For Existing Tables)
If you already created the `allowed_users` table, run this SQL script to add the new columns:

```sql
-- Add role and is_active columns to allowed_users
alter table allowed_users 
  add column if not exists role text default 'regular' check (role in ('admin', 'regular')),
  add column if not exists is_active boolean default true not null;
```

> [!TIP]
> The bot implements a **graceful fallback**: if the `allowed_users` table is empty or does not exist, it automatically falls back to validating users against the `TELEGRAM_ALLOWED_USER_ID`, `TELEGRAM_ALLOWED_USER_IDS`, and `TELEGRAM_CHAT_ID` environment variables in Vercel.

---

## 3. Configure Environment Variables

For the Supabase client in [db.py](file:///mnt/c/Users/Ashish/Downloads/playground/daily-telegram-insights/src/db.py) to connect, define the following variables:

### Local Development
Add the following keys to your [.env](file:///mnt/c/Users/Ashish/Downloads/playground/daily-telegram-insights/.env) file:
```env
SUPABASE_URL="https://your-project-ref.supabase.co"
SUPABASE_SERVICE_ROLE_KEY="your-secret-service-role-key"
```

### Vercel Production
Add these same variables to your Vercel Project Settings under **Environment Variables**:
- **`SUPABASE_URL`**: Found in Supabase Dashboard -> **Project Settings** -> **API** -> **Project URL**.
- **`SUPABASE_SERVICE_ROLE_KEY`**: Found in Supabase Dashboard -> **Project Settings** -> **API** -> **Project API Keys** (under `service_role` / `secret`).
