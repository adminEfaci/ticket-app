#!/usr/bin/env python3
"""
Fix upload_router.py to use User objects instead of dicts
"""

import re

# Read the file
with open('/app/backend/routers/upload_router.py', 'r') as f:
    content = f.read()

# Define replacements
replacements = [
    # Change dict type hints to User
    (r'current_user: dict = Depends\(get_current_user\)', 
     'current_user: User = Depends(get_current_user)'),
    (r'current_user: dict = Depends\(RoleChecker\(\[UserRole\.ADMIN, UserRole\.MANAGER\]\)\)', 
     'current_user: User = Depends(RoleChecker([UserRole.ADMIN, UserRole.MANAGER]))'),
    
    # Change dict subscripts to attributes
    (r"current_user\[\"user_id\"\]", "current_user.id"),
    (r"current_user\['user_id'\]", "current_user.id"),
    (r"current_user\[\"role\"\]", "current_user.role.value"),
    (r"current_user\['role'\]", "current_user.role.value"),
    (r"current_user\.get\('client_id'\)", "getattr(current_user, 'client_id', None)"),
    (r"current_user\.get\(\"client_id\"\)", "getattr(current_user, 'client_id', None)"),
]

# Apply replacements
for old, new in replacements:
    content = re.sub(old, new, content)

# Add User import if not present
if 'from backend.models.user import User' not in content:
    # Find the imports section and add it
    import_section = content.find('from backend.middleware.auth_middleware')
    if import_section != -1:
        line_start = content.rfind('\n', 0, import_section)
        content = content[:line_start] + '\nfrom backend.models.user import User' + content[line_start:]

# Write the file back
with open('/app/backend/routers/upload_router.py', 'w') as f:
    f.write(content)

print("Fixed upload_router.py")