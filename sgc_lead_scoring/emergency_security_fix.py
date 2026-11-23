#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Emergency Fix for llm_lead_scoring Security Groups
===================================================

ISSUE: SGC TECH AI deployment has old security/ir.model.access.csv with deprecated groups
FIX: Update security groups from crm.group_crm_* to sales_team.group_sale_*

This script ensures the correct Odoo 17 security groups are in place.
"""

import os
import sys
from pathlib import Path

# ANSI color codes
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
BOLD = '\033[1m'
RESET = '\033[0m'

def print_header():
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}{BLUE}🚨 Emergency Security Groups Fix - llm_lead_scoring{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def get_module_path():
    """Get the llm_lead_scoring module path"""
    current_dir = Path(__file__).resolve().parent
    
    # If running from within llm_lead_scoring
    if current_dir.name == 'llm_lead_scoring':
        return current_dir
    
    # If running from parent directory
    module_path = current_dir / 'llm_lead_scoring'
    if module_path.exists():
        return module_path
    
    print(f"{RED}❌ Error: Could not find llm_lead_scoring module{RESET}")
    sys.exit(1)

def backup_file(file_path):
    """Create backup of original file"""
    backup_path = file_path.parent / f"{file_path.name}.backup"
    if file_path.exists() and not backup_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        with open(backup_path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"{GREEN}✅ Backup created: {backup_path.name}{RESET}")
        return True
    return False

def fix_security_csv(module_path):
    """Fix the ir.model.access.csv file"""
    security_file = module_path / 'security' / 'ir.model.access.csv'
    
    if not security_file.exists():
        print(f"{RED}❌ Error: File not found: {security_file}{RESET}")
        return False
    
    print(f"\n{YELLOW}📄 Processing: {security_file}{RESET}\n")
    
    # Read current content
    with open(security_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Check if file has deprecated groups
    if 'crm.group_crm_user' in content or 'crm.group_crm_manager' in content:
        print(f"{YELLOW}⚠️  Found deprecated security groups!{RESET}")
        
        # Backup original
        backup_file(security_file)
        
        # Replace deprecated groups with correct Odoo 17 groups
        old_content = content
        content = content.replace('crm.group_crm_user', 'sales_team.group_sale_salesman')
        content = content.replace('crm.group_crm_manager', 'sales_team.group_sale_manager')
        
        # Write fixed content
        with open(security_file, 'w', encoding='utf-8') as f:
            f.write(content)
        
        print(f"{GREEN}✅ Fixed security groups:{RESET}")
        print(f"   {RED}crm.group_crm_user{RESET} → {GREEN}sales_team.group_sale_salesman{RESET}")
        print(f"   {RED}crm.group_crm_manager{RESET} → {GREEN}sales_team.group_sale_manager{RESET}")
        
        return True
    else:
        print(f"{GREEN}✅ Security groups already correct!{RESET}")
        return True

def verify_fix(module_path):
    """Verify the fix was applied correctly"""
    security_file = module_path / 'security' / 'ir.model.access.csv'
    
    with open(security_file, 'r', encoding='utf-8') as f:
        content = f.read()
    
    print(f"\n{BOLD}📋 Verification:{RESET}")
    
    # Check for deprecated groups
    has_old_groups = 'crm.group_crm_user' in content or 'crm.group_crm_manager' in content
    has_new_groups = 'sales_team.group_sale_salesman' in content or 'sales_team.group_sale_manager' in content
    
    if has_old_groups:
        print(f"{RED}❌ Still contains deprecated groups!{RESET}")
        return False
    elif has_new_groups:
        print(f"{GREEN}✅ Using correct Odoo 17 security groups{RESET}")
        print(f"{GREEN}✅ No deprecated groups found{RESET}")
        return True
    else:
        print(f"{YELLOW}⚠️  Warning: No security groups found{RESET}")
        return False

def print_deployment_instructions():
    """Print deployment instructions for CloudPepper"""
    print(f"\n{BOLD}{BLUE}{'='*70}{RESET}")
    print(f"{BOLD}📦 SGC TECH AI deployment Instructions:{RESET}\n")
    
    print(f"{BOLD}Option 1: Update Module via Web UI{RESET}")
    print(f"  1. Login to CloudPepper: https://sgctech.ai/")
    print(f"  2. Go to Apps → Update Apps List")
    print(f"  3. Find 'LLM Lead Scoring' → Click 'Upgrade'")
    print(f"  4. Restart Odoo service if needed\n")
    
    print(f"{BOLD}Option 2: Manual File Update{RESET}")
    print(f"  1. Upload fixed security/ir.model.access.csv to server")
    print(f"  2. Path: /var/odoo/sgc_lead_scoring/addons/llm_lead_scoring/security/")
    print(f"  3. Run: ./odoo-bin -d sgc_lead_scoring -u llm_lead_scoring --stop-after-init")
    print(f"  4. Restart Odoo: sudo systemctl restart odoo\n")
    
    print(f"{BOLD}Option 3: Command Line Update{RESET}")
    print(f"  cd /var/odoo/sgc_lead_scoring/addons/llm_lead_scoring")
    print(f"  python3 emergency_security_fix.py")
    print(f"  ./odoo-bin -d sgc_lead_scoring -u llm_lead_scoring --stop-after-init")
    print(f"  sudo systemctl restart odoo\n")
    
    print(f"{YELLOW}⚠️  IMPORTANT: After update, you MUST upgrade the module in Odoo!{RESET}")
    print(f"{BOLD}{BLUE}{'='*70}{RESET}\n")

def print_fixed_csv():
    """Print the correct CSV content"""
    print(f"\n{BOLD}📄 Correct ir.model.access.csv Content:{RESET}\n")
    print(f"{BLUE}{'─'*70}{RESET}")
    
    correct_csv = """id,name,model_id:id,group_id:id,perm_read,perm_write,perm_create,perm_unlink
access_llm_provider_user,llm.provider.user,model_llm_provider,sales_team.group_sale_salesman,1,0,0,0
access_llm_provider_manager,llm.provider.manager,model_llm_provider,sales_team.group_sale_manager,1,1,1,1
access_llm_service_user,llm.service.user,model_llm_service,sales_team.group_sale_salesman,1,0,0,0
access_lead_enrichment_wizard_user,lead.enrichment.wizard.user,model_lead_enrichment_wizard,sales_team.group_sale_salesman,1,1,1,1"""
    
    print(correct_csv)
    print(f"{BLUE}{'─'*70}{RESET}\n")

def main():
    """Main execution"""
    print_header()
    
    # Get module path
    module_path = get_module_path()
    print(f"{BLUE}📁 Module Path: {module_path}{RESET}\n")
    
    # Fix security CSV
    success = fix_security_csv(module_path)
    
    if success:
        # Verify fix
        if verify_fix(module_path):
            print(f"\n{GREEN}{BOLD}{'='*70}{RESET}")
            print(f"{GREEN}{BOLD}✅ Security Groups Fix Applied Successfully!{RESET}")
            print(f"{GREEN}{BOLD}{'='*70}{RESET}")
            
            # Show correct CSV
            print_fixed_csv()
            
            # Show deployment instructions
            print_deployment_instructions()
            
            print(f"{GREEN}✅ Fix complete! Ready for SGC TECH AI deployment.{RESET}\n")
            return 0
        else:
            print(f"\n{RED}❌ Verification failed!{RESET}")
            return 1
    else:
        print(f"\n{RED}❌ Fix failed!{RESET}")
        return 1

if __name__ == '__main__':
    sys.exit(main())
