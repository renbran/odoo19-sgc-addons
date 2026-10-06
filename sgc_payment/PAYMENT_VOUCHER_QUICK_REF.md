# Payment Voucher - Quick Reference

## 🚀 Quick Deploy

```bash
docker-compose exec odoo odoo --update=payment_account_enhanced --stop-after-init && docker-compose restart odoo
```

## ✅ What's New

**Professional Payment Voucher** - Clean, modern, fully usable template

- ✅ Single-page A4 format
- ✅ Large, clear amount display
- ✅ Color-coded status badges
- ✅ Signature blocks for approvals
- ✅ QR code integration
- ✅ Workflow progress indicator
- ✅ Professional burgundy design

## 📋 How to Use

1. **Open Payment**: Accounting → Vendors/Customers → Payments
2. **Select Payment**: Click on payment record
3. **Print**: Click Print → "Professional Payment Voucher"
4. **Done**: PDF generated ready for printing/signing

## 🎨 What You'll See

### Header
- Company name
- Document type (RECEIPT/PAYMENT)
- Document number
- Status badge (Posted/Draft/Cancelled)

### Body
- Payee/recipient information
- Payment date and method
- Reference number
- **FEATURED AMOUNT** (large, prominent)
- Amount in words
- QR code (if available)

### Workflow
- Visual progress: Reviewed → Approved → Authorized → Posted

### Signatures
- Reviewed By (with date)
- Approved By (with date)
- Authorized By (with date)
- Received By (recipient)

### Footer
- Document ID
- Reference
- Generation timestamp

## 🔧 Quick Fixes

### Report Not Showing?
```bash
docker-compose exec odoo odoo --update=payment_account_enhanced --stop-after-init
docker-compose restart odoo
# Clear browser cache: Ctrl+Shift+R
```

### QR Code Missing?
```bash
docker-compose exec odoo pip install qrcode Pillow
docker-compose restart odoo
```

### Colors Not Printing?
Enable "Background graphics" in print settings

## 📊 Available Templates

1. **Professional** (NEW - Recommended) - Clean, readable
2. **Burgundy Premium** - Ultra-compact
3. **Enhanced A4** - Maximum detail

## ✅ Test Checklist

- [ ] Print posted payment (green badge)
- [ ] Print draft payment (orange badge)
- [ ] Print receipt (inbound)
- [ ] Print payment (outbound)
- [ ] Verify signatures populate
- [ ] Check amount displays correctly
- [ ] Confirm QR code shows
- [ ] Test actual printing

## 📞 Files

- Template: `reports/payment_voucher_professional.xml`
- Manifest: `__manifest__.py`
- Guide: `PAYMENT_VOUCHER_DEPLOYMENT_GUIDE.md`

---

**Status**: ✅ Ready for Production  
**Time**: 5-10 minutes  
**Risk**: Low
