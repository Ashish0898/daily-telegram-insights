# Supabase Setup Guide for Request Auditing

To successfully log webhook and cron scheduler requests, you need to create/update the audit table in your Supabase project and configure the environment variables on Vercel and locally.

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

## 2. Configure Environment Variables

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
