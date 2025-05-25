#!/usr/bin/env python3
"""
Fix all routers to use User objects instead of dicts
"""

import os
import re
import glob

def fix_router_file(filepath):
    """Fix a single router file"""
    print(f"Fixing {filepath}...")
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    original_content = content
    
    # Define replacements
    replacements = [
        # Change dict type hints to User
        (r'current_user: dict = Depends\(get_current_user\)', 
         'current_user: User = Depends(get_current_user)'),
        (r'current_user: dict = Depends\(authenticated_required\(\)\)', 
         'current_user: User = Depends(authenticated_required())'),
        (r'current_user: dict = Depends\(admin_required\(\)\)', 
         'current_user: User = Depends(admin_required())'),
        (r'current_user: dict = Depends\(RoleChecker\((.*?)\)\)', 
         r'current_user: User = Depends(RoleChecker(\1))'),
        
        # Change dict subscripts to attributes
        (r"current_user\[[\"\']user_id[\"\']\]", "current_user.id"),
        (r"current_user\[[\"\']role[\"\']\]", "current_user.role.value"),
        (r"current_user\.get\(['\"]client_id['\"]\)", "getattr(current_user, 'client_id', None)"),
        (r"current_user\.get\(['\"]user_id['\"]\)", "current_user.id"),
        (r"current_user\.get\(['\"]role['\"]\)", "current_user.role.value"),
    ]
    
    # Apply replacements
    for old, new in replacements:
        content = re.sub(old, new, content)
    
    # Add User import if needed and not present
    if 'current_user: User' in content and 'from backend.models.user import User' not in content:
        # Find where to add the import
        import_lines = []
        lines = content.split('\n')
        import_section_end = 0
        
        for i, line in enumerate(lines):
            if line.startswith('from ') or line.startswith('import '):
                import_section_end = i
        
        # Add after the last import
        if import_section_end > 0:
            lines.insert(import_section_end + 1, 'from backend.models.user import User')
            content = '\n'.join(lines)
    
    # Only write if changed
    if content != original_content:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"  ✓ Fixed {filepath}")
    else:
        print(f"  - No changes needed for {filepath}")

def main():
    """Fix all router files"""
    router_dir = "/app/backend/routers"
    router_files = glob.glob(os.path.join(router_dir, "*_router.py"))
    
    print(f"Found {len(router_files)} router files to check")
    
    for router_file in router_files:
        try:
            fix_router_file(router_file)
        except Exception as e:
            print(f"  ✗ Error fixing {router_file}: {e}")
    
    print("\nDone!")

if __name__ == "__main__":
    main()