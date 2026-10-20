#!/bin/bash
echo "=========================================="
echo "🚀 INFINITY ERP: GOODS RECEIVING VALIDATION"
echo "=========================================="

BASE_URL="http://127.0.0.1:8000"

check_po_status() {
    python3 -c "
from database import SessionLocal
import models
db = SessionLocal()
po = db.query(models.PurchaseOrder).filter(models.PurchaseOrder.id == 1).first()
print(po.status if po else 'NOT FOUND')
db.close()
"
}

echo ""
echo "TEST 1: Partial Delivery (Receive 5 of 10 Laptops)"
echo "--------------------------------------------------"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/receipts" \
  -F "receipt_number=FINAL-TEST-001" \
  -F "po_id=1" \
  -F "line_ids=1" -F "line_ids=2" \
  -F "received_qtys=5" -F "received_qtys=0" \
  -F "notes=Partial delivery test")

if [ "$RESPONSE" == "303" ]; then echo "✅ PASS: Receipt created (HTTP 303)"; else echo "❌ FAIL: Expected 303, got $RESPONSE"; fi

STATUS=$(check_po_status)
if [ "$STATUS" == "PARTIALLY_RECEIVED" ]; then echo "✅ PASS: PO Status updated to 'PARTIALLY_RECEIVED'"; else echo "❌ FAIL: Expected 'PARTIALLY_RECEIVED', got '$STATUS'"; fi

echo ""
echo "TEST 2: Complete Delivery (Receive remaining 5 Laptops AND 50 Mice)"
echo "-------------------------------------------------------------------"
RESPONSE=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$BASE_URL/api/receipts" \
  -F "receipt_number=FINAL-TEST-002" \
  -F "po_id=1" \
  -F "line_ids=1" -F "line_ids=2" \
  -F "received_qtys=5" -F "received_qtys=50" \
  -F "notes=Final delivery of all items")

if [ "$RESPONSE" == "303" ]; then echo "✅ PASS: Final receipt created (HTTP 303)"; else echo "❌ FAIL: Expected 303, got $RESPONSE"; fi

STATUS=$(check_po_status)
if [ "$STATUS" == "RECEIVED" ]; then echo "✅ PASS: PO Status correctly updated to 'RECEIVED'"; else echo "❌ FAIL: Expected 'RECEIVED', got '$STATUS'"; fi

echo ""
echo "TEST 3: Quantity Protection (Try to over-receive)"
echo "-------------------------------------------------"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/receipts" \
  -F "receipt_number=FINAL-TEST-003" \
  -F "po_id=1" \
  -F "line_ids=1" \
  -F "received_qtys=999" \
  -F "notes=Should be rejected")

if [[ "$RESPONSE" == *"Cannot receive"* ]] || [[ "$RESPONSE" == *"400"* ]]; then echo "✅ PASS: System correctly rejected over-receiving (HTTP 400)"; else echo "❌ FAIL: System allowed over-receiving!"; fi

echo ""
echo "TEST 4: Duplicate Receipt Number Protection"
echo "-------------------------------------------"
RESPONSE=$(curl -s -X POST "$BASE_URL/api/receipts" \
  -F "receipt_number=FINAL-TEST-001" \
  -F "po_id=1" \
  -F "line_ids=1" \
  -F "received_qtys=1" \
  -F "notes=Should be rejected")

if [[ "$RESPONSE" == *"already exists"* ]] || [[ "$RESPONSE" == *"400"* ]]; then echo "✅ PASS: System correctly rejected duplicate receipt (HTTP 400)"; else echo "❌ FAIL: System allowed duplicate receipt!"; fi

echo ""
echo "=========================================="
echo "🎉 VALIDATION COMPLETE"
echo "=========================================="
