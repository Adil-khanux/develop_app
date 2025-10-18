import frappe
from collections import defaultdict

def create_purchase_invoice(doc, method):
    # 1. Initializes a dictionary to group items by supplier.  
#     # {
#   "Supplier A": [item1, item2],
#   "Supplier B": [item3]
# }

    supplier_items_map = defaultdict(list)

    # Step 2: Iterates over each item in the document sales invoice and check each item in sales voice is consingment or not 
    for item in doc.items:
        item_type = frappe.db.get_value("Item", item.item_code, "custom_item_type")
        if item_type != "Consignment":
            frappe.msgprint(f"Item {item.item_code} is not Consignment")
            continue

#  3 .T racks how much quantity still needs to be billed for this item.
        remaining_qty = item.qty

#  4 . Fetch unbilled Purchase Receipts for this item
        receipts = frappe.db.sql("""
            SELECT 
                pri.parent AS purchase_receipt,  
                pri.rate,
                pri.item_code,
                pri.name as row_name,
                pri.received_qty,
                (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) AS remaining_qty,
                pr.name,
                pr.supplier         
            FROM `tabPurchase Receipt Item` AS pri
            JOIN `tabPurchase Receipt` AS pr
                ON pr.name = pri.parent
            WHERE pri.item_code = %s 
                AND pr.docstatus = 1
                AND (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) > 0
            ORDER BY pr.posting_date ASC
        """, (item.item_code,), as_dict=True)

# 5 . receipts naam ke list ke andar iterate karta hai : har receipt ko check krega 
        for receipt in receipts:
# 6.   Stop if we’ve already billed the full quantity. 
            if remaining_qty <= 0:
                break
#         receipt m S BACHI HUI  qty lenge 
            qty_to_bill = min(remaining_qty, receipt["remaining_qty"])
            remaining_qty -= qty_to_bill

            supplier_items_map[receipt["supplier"]].append({
                "item_code": receipt["item_code"],
                "rate": receipt["rate"],
                "qty": qty_to_bill,
                "purchase_receipt": receipt["name"],
                "pr_detail": receipt["row_name"]
            })

    # Step 8: Create one invoice per supplier
    for supplier, items in supplier_items_map.items():
        pi = frappe.new_doc("Purchase Invoice")
        pi.supplier = supplier

        for item in items:
            pi.append("items", item)

        pi.insert()
        pi.submit()
        frappe.msgprint(f"Purchase Invoice {pi.name} created for supplier {supplier}")
