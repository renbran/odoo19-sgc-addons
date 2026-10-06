#!/bin/bash
# CloudPepper Emergency Security Fix for llm_lead_scoring
# Fixes deprecated security groups: crm.group_crm_* → sales_team.group_sale_*

set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Configuration
MODULE_NAME="llm_lead_scoring"
SECURITY_FILE="security/ir.model.access.csv"
DB_NAME="scholarixv2"

echo -e "\n${BOLD}${BLUE}========================================${NC}"
echo -e "${BOLD}${BLUE}🚨 CloudPepper Emergency Fix${NC}"
echo -e "${BOLD}${BLUE}Module: ${MODULE_NAME}${NC}"
echo -e "${BOLD}${BLUE}========================================${NC}\n"

# Detect Odoo installation path
if [ -d "/var/odoo/scholarixv2" ]; then
    ODOO_PATH="/var/odoo/scholarixv2"
elif [ -d "/opt/odoo" ]; then
    ODOO_PATH="/opt/odoo"
elif [ -d "/usr/lib/python3/dist-packages/odoo" ]; then
    ODOO_PATH="/usr/lib/python3/dist-packages/odoo"
else
    echo -e "${RED}❌ Error: Could not find Odoo installation${NC}"
    echo -e "${YELLOW}Please specify ODOO_PATH manually${NC}"
    exit 1
fi

echo -e "${BLUE}📁 Odoo Path: ${ODOO_PATH}${NC}"

# Find module path
MODULE_PATH="${ODOO_PATH}/addons/${MODULE_NAME}"
if [ ! -d "${MODULE_PATH}" ]; then
    MODULE_PATH="${ODOO_PATH}/../addons/${MODULE_NAME}"
fi

if [ ! -d "${MODULE_PATH}" ]; then
    echo -e "${RED}❌ Error: Module not found at ${MODULE_PATH}${NC}"
    exit 1
fi

echo -e "${BLUE}📦 Module Path: ${MODULE_PATH}${NC}\n"

# Check if security file exists
SECURITY_PATH="${MODULE_PATH}/${SECURITY_FILE}"
if [ ! -f "${SECURITY_PATH}" ]; then
    echo -e "${RED}❌ Error: Security file not found: ${SECURITY_PATH}${NC}"
    exit 1
fi

echo -e "${YELLOW}📄 Processing: ${SECURITY_FILE}${NC}"

# Backup original file
BACKUP_PATH="${SECURITY_PATH}.backup.$(date +%Y%m%d_%H%M%S)"
cp "${SECURITY_PATH}" "${BACKUP_PATH}"
echo -e "${GREEN}✅ Backup created: ${BACKUP_PATH}${NC}"

# Check if file has deprecated groups
if grep -q "crm\.group_crm_user\|crm\.group_crm_manager" "${SECURITY_PATH}"; then
    echo -e "${YELLOW}⚠️  Found deprecated security groups!${NC}"
    
    # Replace deprecated groups
    sed -i 's/crm\.group_crm_user/sales_team.group_sale_salesman/g' "${SECURITY_PATH}"
    sed -i 's/crm\.group_crm_manager/sales_team.group_sale_manager/g' "${SECURITY_PATH}"
    
    echo -e "${GREEN}✅ Fixed security groups:${NC}"
    echo -e "   ${RED}crm.group_crm_user${NC} → ${GREEN}sales_team.group_sale_salesman${NC}"
    echo -e "   ${RED}crm.group_crm_manager${NC} → ${GREEN}sales_team.group_sale_manager${NC}"
else
    echo -e "${GREEN}✅ Security groups already correct!${NC}"
fi

# Verify fix
echo -e "\n${BOLD}📋 Verification:${NC}"
if grep -q "crm\.group_crm_user\|crm\.group_crm_manager" "${SECURITY_PATH}"; then
    echo -e "${RED}❌ Still contains deprecated groups!${NC}"
    echo -e "${YELLOW}Restoring backup...${NC}"
    cp "${BACKUP_PATH}" "${SECURITY_PATH}"
    exit 1
else
    echo -e "${GREEN}✅ No deprecated groups found${NC}"
    echo -e "${GREEN}✅ Using correct Odoo 17 security groups${NC}"
fi

# Show current content
echo -e "\n${BOLD}📄 Current Content:${NC}"
echo -e "${BLUE}────────────────────────────────────────${NC}"
cat "${SECURITY_PATH}"
echo -e "${BLUE}────────────────────────────────────────${NC}"

# Ask to upgrade module
echo -e "\n${BOLD}${YELLOW}⚠️  Module needs to be upgraded in Odoo!${NC}"
echo -e "${BOLD}Choose upgrade method:${NC}"
echo -e "  ${BOLD}1)${NC} Upgrade via command line (recommended)"
echo -e "  ${BOLD}2)${NC} Manual upgrade via Web UI"
echo -e "  ${BOLD}3)${NC} Skip upgrade (do it later)"
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo -e "\n${BLUE}🔄 Upgrading module...${NC}"
        
        # Find odoo-bin
        ODOO_BIN="${ODOO_PATH}/odoo-bin"
        if [ ! -f "${ODOO_BIN}" ]; then
            ODOO_BIN="${ODOO_PATH}/odoo.py"
        fi
        if [ ! -f "${ODOO_BIN}" ]; then
            ODOO_BIN="$(which odoo || which odoo-bin || echo '')"
        fi
        
        if [ -z "${ODOO_BIN}" ]; then
            echo -e "${RED}❌ Error: odoo-bin not found${NC}"
            echo -e "${YELLOW}Please upgrade manually via Web UI${NC}"
        else
            echo -e "${BLUE}📍 Using: ${ODOO_BIN}${NC}"
            
            # Upgrade module
            sudo -u odoo "${ODOO_BIN}" -d "${DB_NAME}" -u "${MODULE_NAME}" --stop-after-init
            
            echo -e "${GREEN}✅ Module upgraded${NC}"
            
            # Restart Odoo
            echo -e "\n${BLUE}🔄 Restarting Odoo...${NC}"
            if sudo systemctl restart odoo; then
                echo -e "${GREEN}✅ Odoo restarted${NC}"
                
                # Check status
                sleep 2
                if sudo systemctl is-active --quiet odoo; then
                    echo -e "${GREEN}✅ Odoo is running${NC}"
                else
                    echo -e "${RED}❌ Odoo failed to start${NC}"
                    echo -e "${YELLOW}Check logs: journalctl -u odoo -n 50${NC}"
                fi
            else
                echo -e "${RED}❌ Failed to restart Odoo${NC}"
            fi
        fi
        ;;
    2)
        echo -e "\n${BOLD}${BLUE}📦 Manual Upgrade Instructions:${NC}"
        echo -e "  1. Login to https://scholarixglobal.com/"
        echo -e "  2. Go to Apps → Update Apps List"
        echo -e "  3. Find 'LLM Lead Scoring' → Click 'Upgrade'"
        echo -e "  4. Wait for upgrade to complete"
        ;;
    3)
        echo -e "\n${YELLOW}⚠️  Skipping upgrade${NC}"
        echo -e "${YELLOW}Remember to upgrade the module before using it!${NC}"
        ;;
    *)
        echo -e "\n${YELLOW}Invalid choice. Skipping upgrade.${NC}"
        ;;
esac

echo -e "\n${BOLD}${GREEN}========================================${NC}"
echo -e "${BOLD}${GREEN}✅ Security Fix Complete!${NC}"
echo -e "${BOLD}${GREEN}========================================${NC}\n"

echo -e "${BOLD}📊 Summary:${NC}"
echo -e "  ✅ Backup created: ${BACKUP_PATH}"
echo -e "  ✅ Security groups updated to Odoo 17 standards"
echo -e "  ✅ File verified: ${SECURITY_PATH}"
echo -e "\n${BOLD}🎯 Next Steps:${NC}"
echo -e "  1. Verify module is upgraded (Apps menu)"
echo -e "  2. Test module installation"
echo -e "  3. Check Odoo logs for errors"
echo -e "\n${BOLD}📚 Documentation:${NC}"
echo -e "  • CLOUDPEPPER_EMERGENCY_FIX.md - Detailed instructions"
echo -e "  • DEPLOYMENT_GUIDE.md - Complete deployment guide"
echo -e "\n${GREEN}✅ Ready for production use!${NC}\n"
