import html
import logging
from src.db import allow_user, revoke_user, get_all_users

logger = logging.getLogger("admin_handlers")

def generate_users_html_table(users: list[dict]) -> str:
    """
    Renders an HTML control table page for registered users.
    """
    rows_html = ""
    for u in users:
        uid = u.get("user_id", "")
        uname = u.get("username", "") or ""
        uname_display = f"@{uname}" if uname else "<i>N/A</i>"
        role = u.get("role", "regular")
        active = u.get("is_active", True)
        
        role_badge = f'<span class="badge badge-{role}">{role}</span>'
        status_badge = '<span class="badge badge-active">Active</span>' if active else '<span class="badge badge-inactive">Inactive</span>'
        
        rows_html += f"""
        <tr>
            <td><code>{uid}</code></td>
            <td>{uname_display}</td>
            <td>{role_badge}</td>
            <td>{status_badge}</td>
            <td>{u.get("created_at", "")[:19].replace("T", " ")}</td>
        </tr>
        """
        
    html_page = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>Registered Users List</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
            background-color: #0f172a;
            color: #e2e8f0;
            padding: 40px 20px;
            margin: 0;
            display: flex;
            justify-content: center;
        }}
        .container {{
            width: 100%;
            max-width: 900px;
            background-color: #1e293b;
            border-radius: 12px;
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.1), 0 2px 4px -1px rgba(0, 0, 0, 0.06);
            padding: 30px;
            border: 1px solid #334155;
            box-sizing: border-box;
        }}
        h1 {{
            margin-top: 0;
            font-size: 24px;
            color: #f8fafc;
            border-bottom: 2px solid #334155;
            padding-bottom: 15px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .table-responsive {{
            width: 100%;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            text-align: left;
            min-width: 600px;
        }}
        th, td {{
            padding: 12px 16px;
            border-bottom: 1px solid #334155;
        }}
        th {{
            background-color: #0f172a;
            color: #94a3b8;
            font-weight: 600;
            text-transform: uppercase;
            font-size: 12px;
            letter-spacing: 0.05em;
        }}
        tr:hover {{
            background-color: #334155;
        }}
        code {{
            background-color: #0f172a;
            padding: 2px 6px;
            border-radius: 4px;
            color: #38bdf8;
            font-family: SFMono-Regular, Consolas, "Liberation Mono", Menlo, monospace;
        }}
        .badge {{
            display: inline-block;
            padding: 4px 8px;
            border-radius: 9999px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }}
        .badge-admin {{
            background-color: rgba(239, 68, 68, 0.2);
            color: #ef4444;
            border: 1px solid rgba(239, 68, 68, 0.4);
        }}
        .badge-regular {{
            background-color: rgba(59, 130, 246, 0.2);
            color: #3b82f6;
            border: 1px solid rgba(59, 130, 246, 0.4);
        }}
        .badge-active {{
            background-color: rgba(34, 197, 94, 0.2);
            color: #22c55e;
            border: 1px solid rgba(34, 197, 94, 0.4);
        }}
        .badge-inactive {{
            background-color: rgba(107, 114, 128, 0.2);
            color: #9ca3af;
            border: 1px solid rgba(107, 114, 128, 0.4);
        }}
        @media (max-width: 640px) {{
            body {{
                padding: 10px 5px;
            }}
            .container {{
                padding: 15px 10px;
                border-radius: 8px;
            }}
            h1 {{
                font-size: 18px;
                margin-bottom: 15px;
            }}
            th, td {{
                padding: 10px 8px;
                font-size: 12px;
            }}
            .badge {{
                padding: 2px 6px;
                font-size: 9px;
            }}
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>🛡️ Registered Users Control List</h1>
        <div class="table-responsive">
            <table>
                <thead>
                    <tr>
                        <th>User ID</th>
                        <th>Username</th>
                        <th>Role</th>
                        <th>Status</th>
                        <th>Registered At</th>
                    </tr>
                </thead>
                <tbody>
                    {rows_html}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
"""
    return html_page

def execute_users_get(query_params: dict, is_admin: bool) -> tuple[int, str | dict, str]:
    """
    Executes user retrieval logic. Returns (status_code, content, content_type).
    """
    if not is_admin:
        return 403, {"error": "Access Denied: Administrator privileges required"}, "application/json"

    users = get_all_users()
    if users is None:
        return 500, {"error": "Failed to retrieve users from database"}, "application/json"

    format_type = query_params.get("format", ["json"])[0]
    if format_type == "html":
        html_content = generate_users_html_table(users)
        return 200, html_content, "text/html"
    
    return 200, {"users": users}, "application/json"

def execute_api_allow_user(body: dict) -> tuple[int, dict]:
    """
    Executes administrative user-allow logic. Returns (status_code, response_json).
    """
    try:
        user_id = int(body.get("user_id"))
        username = body.get("username")
        role = body.get("role", "regular")
        email = body.get("email")
        
        success, err_msg = allow_user(user_id, username, role, email)
        if success:
            return 200, {"ok": True}
        else:
            return 500, {"error": err_msg or "Failed to update user in database."}
    except Exception as e:
        return 400, {"error": f"Invalid request body: {str(e)}"}

def execute_api_revoke_user(body: dict) -> tuple[int, dict]:
    """
    Executes administrative user-revoke logic. Returns (status_code, response_json).
    """
    try:
        user_id = int(body.get("user_id"))
        
        success, err_msg = revoke_user(user_id)
        if success:
            return 200, {"ok": True}
        else:
            return 500, {"error": err_msg or "Failed to deactivate user in database."}
    except Exception as e:
        return 400, {"error": f"Invalid request body: {str(e)}"}
