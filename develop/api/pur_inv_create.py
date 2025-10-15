import frappe

def create_purchase_invoice(doc, method):
    for item in doc.items:  # Use doc.items, not items
        # Get item type
        item_type = frappe.db.get_value("Item", item.item_code, "custom_item_type")
        # frappe.msgprint(f"item type is { item_type }")
        
        if item_type != "Consignment":
            frappe.msgprint(f"Item {item.item_code} is not Consignment")
            continue  # skip non-consignment items
        
        # Get oldest Purchase Receipt for this item
        older_receipt = frappe.db.sql("""
            SELECT 
                pri.parent AS purchase_receipt,  
                pri.rate,
                pri.item_code,
                pr.name,
                pr.supplier         
            FROM `tabPurchase Receipt Item` AS pri
            JOIN `tabPurchase Receipt` AS pr
                ON pr.name = pri.parent
            WHERE pri.item_code = %s
            ORDER BY pr.posting_date ASC
            LIMIT 1
        """, (item.item_code,), as_dict=True)
        
        if not older_receipt:
            # frappe.msgprint(f"No Purchase Receipt found for item {item.item_code}")
            continue
        pi = frappe.new_doc("Purchase Invoice")
        #  pick  first receipt from dictionary 
        receipt = older_receipt[0]
        
        # Create new Purchase Invoice
        pi.supplier = receipt["supplier"]  # supplier from parent Purchase Receipt
        
        # Append item
        pi.append("items", {
            "item_code": receipt["item_code"],
            "rate": receipt["rate"],
            "qty": item.qty  ,
            "purchase_receipt" : receipt["name"],
           
        })
        # Save and submit
        pi.insert()
        pi.submit()
        frappe.msgprint(f"Purchase Invoice {pi.name} created for item {item.item_code}")
