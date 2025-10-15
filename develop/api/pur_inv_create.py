import frappe

def create_purchase_invoice(doc, method):
    for item in doc.items:
        item_type = frappe.db.get_value("Item", item.item_code, "custom_item_type")
        if item_type != "Consignment":
            frappe.msgprint(f"Item {item.item_code} is not Consignment")
            continue

        remaining_qty = item.qty
        created_invoices = {}

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


        for receipt in receipts:
            if remaining_qty <= 0:
                break

            grn = receipt["name"]
            supplier = receipt["supplier"]
            available_qty = receipt["remaining_qty"]

            if supplier not in created_invoices:
                pi = frappe.new_doc("Purchase Invoice")
                pi.supplier = supplier
                created_invoices[supplier] = pi
            else:
                pi = created_invoices[supplier]

            qty_to_bill = min(remaining_qty, available_qty)
            remaining_qty -= qty_to_bill

            pi.append("items", {
                "item_code": receipt["item_code"],
                "rate": receipt["rate"],
                "qty": qty_to_bill,
                "purchase_receipt": grn,
                "pr_detail": receipt["row_name"]
            })

        for supplier, pi in created_invoices.items():
            pi.insert()
            pi.submit()
            frappe.msgprint(f"Purchase Invoice {pi.name} created for supplier {supplier}")
