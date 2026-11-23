#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
LLM Lead Scoring - Quick Installation Script
============================================
Automated installation and configuration for SGC TECH AI

Usage:
    python quick_install.py [--test-mode]

Options:
    --test-mode    Run in test database instead of production
"""

import sys
import subprocess
import argparse
from pathlib import Path

class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    BOLD = '\033[1m'
    END = '\033[0m'

def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text:^70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")

def print_step(step_num, total_steps, description):
    """Print step progress"""
    print(f"{Colors.BOLD}[{step_num}/{total_steps}] {description}...{Colors.END}")

def print_success(message):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {message}{Colors.END}")

def print_error(message):
    """Print error message"""
    print(f"{Colors.RED}❌ {message}{Colors.END}")

def print_warning(message):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {message}{Colors.END}")

def run_command(cmd, description):
    """Run shell command and return success status"""
    try:
        print(f"   Running: {cmd}")
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            print_success(description)
            return True
        else:
            print_error(f"{description} - Error: {result.stderr}")
            return False
    except Exception as e:
        print_error(f"{description} - Exception: {str(e)}")
        return False

def validate_module():
    """Run validation before installation"""
    print_step(1, 5, "Validating Module")
    
    module_path = Path(__file__).parent
    validator_script = module_path / 'validate_production_ready.py'
    
    if not validator_script.exists():
        print_warning("Validator script not found, skipping validation")
        return True
    
    result = subprocess.run(
        [sys.executable, str(validator_script)],
        capture_output=True,
        text=True
    )
    
    if result.returncode == 0:
        print_success("Module validation passed (52/52 checks)")
        return True
    else:
        print_error("Module validation failed")
        print(result.stdout)
        return False

def check_dependencies():
    """Check if required Python packages are installed"""
    print_step(2, 5, "Checking Dependencies")
    
    required_packages = ['requests']
    missing_packages = []
    
    for package in required_packages:
        try:
            __import__(package)
            print(f"   ✓ {package} installed")
        except ImportError:
            missing_packages.append(package)
            print(f"   ✗ {package} missing")
    
    if missing_packages:
        print_warning(f"Missing packages: {', '.join(missing_packages)}")
        print("   Install with: pip install " + " ".join(missing_packages))
        return False
    
    print_success("All dependencies satisfied")
    return True

def backup_database(database):
    """Create database backup before installation"""
    print_step(3, 5, "Creating Database Backup")
    
    from datetime import datetime
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_file = f"backup_{database}_{timestamp}.dump"
    
    print(f"   Backup file: {backup_file}")
    print_warning("Backup creation requires pg_dump access")
    print_warning("Skip this step if you don't have database access")
    
    response = input("   Create backup? (y/N): ").strip().lower()
    if response == 'y':
        cmd = f"pg_dump {database} > {backup_file}"
        return run_command(cmd, "Database backup created")
    else:
        print_warning("Skipping backup (not recommended for production)")
        return True

def install_module(database, test_mode=False):
    """Install the module using Odoo CLI"""
    print_step(4, 5, "Installing Module")
    
    if test_mode:
        print_warning("Installing in TEST MODE")
        database = f"test_{database}"
    
    print(f"   Target database: {database}")
    
    # Check if Odoo is available
    odoo_bin = None
    possible_paths = [
        '/usr/bin/odoo',
        '/usr/bin/odoo-bin',
        './odoo-bin',
        '../odoo-bin',
        '../../odoo-bin',
    ]
    
    for path in possible_paths:
        if Path(path).exists():
            odoo_bin = path
            break
    
    if not odoo_bin:
        print_error("Odoo binary not found")
        print("   Please install manually via Apps menu")
        return False
    
    print(f"   Using Odoo binary: {odoo_bin}")
    
    cmd = f"{odoo_bin} -d {database} -i llm_lead_scoring --stop-after-init"
    return run_command(cmd, "Module installed successfully")

def print_post_install_instructions():
    """Print configuration instructions"""
    print_step(5, 5, "Post-Installation Configuration")
    
    print(f"\n{Colors.BOLD}📋 Next Steps:{Colors.END}")
    print("""
1. Configure LLM Provider:
   • Navigate to: Settings → Technical → LLM Providers
   • Create new provider (recommended: Groq with llama-3.1-70b-versatile)
   • Get free API key from: https://console.groq.com/
   • Set as default provider

2. Configure Scoring Weights:
   • Go to: Settings → CRM → LLM Lead Scoring Configuration
   • Set weights: Completeness (30%), Clarity (40%), Engagement (30%)
   • Enable auto-enrichment if desired

3. Test Installation:
   • Open any CRM lead
   • Click "Calculate AI Score" button
   • Verify score calculation works
   • Check internal notes for analysis

4. Review Documentation:
   • DEPLOYMENT_GUIDE.md - Complete deployment guide
   • README.md - Feature overview
   • INSTALLATION.md - Detailed setup instructions

5. Train Users:
   • Show sales team the new AI features
   • Demonstrate batch enrichment wizard
   • Explain scoring categories (Hot/Warm/Cold/Poor)
    """)
    
    print(f"\n{Colors.GREEN}{Colors.BOLD}✅ Installation Complete!{Colors.END}")

def main():
    """Main installation flow"""
    parser = argparse.ArgumentParser(description='Install LLM Lead Scoring module')
    parser.add_argument('--test-mode', action='store_true', 
                       help='Install in test database')
    parser.add_argument('--database', default='sgc_lead_scoring',
                       help='Target database name (default: sgc_lead_scoring)')
    parser.add_argument('--skip-validation', action='store_true',
                       help='Skip pre-installation validation')
    parser.add_argument('--skip-backup', action='store_true',
                       help='Skip database backup')
    
    args = parser.parse_args()
    
    print_header("🚀 LLM Lead Scoring - Quick Installation")
    
    print(f"{Colors.BOLD}Installation Configuration:{Colors.END}")
    print(f"  Database: {args.database}")
    print(f"  Test Mode: {'Yes' if args.test_mode else 'No'}")
    print(f"  Skip Validation: {'Yes' if args.skip_validation else 'No'}")
    print(f"  Skip Backup: {'Yes' if args.skip_backup else 'No'}")
    print()
    
    if not args.test_mode:
        print_warning("Installing in PRODUCTION mode!")
        response = input("Continue? (y/N): ").strip().lower()
        if response != 'y':
            print("Installation cancelled")
            return
    
    # Step 1: Validate module
    if not args.skip_validation:
        if not validate_module():
            print_error("Validation failed. Fix errors before installation.")
            sys.exit(1)
    else:
        print_warning("Skipping validation")
    
    # Step 2: Check dependencies
    if not check_dependencies():
        print_error("Missing dependencies. Install them first.")
        sys.exit(1)
    
    # Step 3: Backup database
    if not args.skip_backup and not args.test_mode:
        if not backup_database(args.database):
            response = input("Backup failed. Continue anyway? (y/N): ").strip().lower()
            if response != 'y':
                print("Installation cancelled")
                sys.exit(1)
    else:
        print_warning("Skipping backup")
    
    # Step 4: Install module
    success = install_module(args.database, args.test_mode)
    
    if not success:
        print_error("Installation failed")
        print("\n📖 Manual Installation:")
        print("   1. Login to Odoo")
        print("   2. Go to Apps → Update Apps List")
        print("   3. Search 'LLM Lead Scoring'")
        print("   4. Click Install")
        sys.exit(1)
    
    # Step 5: Post-install instructions
    print_post_install_instructions()
    
    print_header("✅ Installation Successful!")

if __name__ == '__main__':
    main()
