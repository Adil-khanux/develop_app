supplier_items_map = {}

for item in doc.items:
    # 1. कस्टम आइटम टाइप (Custom Item Type) प्राप्त करें
    item_type = frappe.db.get_value("Item", item.item_code, "custom_item_type")
    
    # 2. अगर आइटम कंसाइनमेंट (Consignment) नहीं है, तो आगे बढ़ें (Skip)
    if item_type != "Consignment":
        continue
    
    remaining_qty = item.qty

    # 3. इस आइटम के लिए बाकी बची Quantity के साथ खरीद रसीदें (Purchase Receipts - PRs) Fetch करें।
    # यह FIFO (First-In, First-Out) क्रम में होना चाहिए।
    receipts = frappe.db.sql("""
        SELECT 
            pri.parent AS purchase_receipt,
            pri.rate,
            pri.item_code,
            pri.name AS row_name,
            pr.supplier,
            # शेष Quantity की गणना करें जो अभी तक बिल नहीं हुई है:
            (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) AS remaining_qty
        FROM 
            `tabPurchase Receipt Item` AS pri
        JOIN 
            `tabPurchase Receipt` AS pr 
        ON 
            pr.name = pri.parent
        WHERE 
            pri.item_code = %s
            AND pr.docstatus = 1
            AND (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) > 0
        ORDER BY 
            pr.posting_date ASC -- FIFO Order के लिए सबसे पुरानी तारीख पहले
    """, (item.item_code,), as_dict=True)

    # 4. खरीद रसीदों (PRs) से बिल करने के लिए Quantity आवंटित करें
    for receipt in receipts:
        if remaining_qty <= 0:
            break
        
        # आवंटित करने के लिए कम से कम Quantity चुनें (बाकी बची ज़रूरत या PR में उपलब्ध Qty)
        qty_to_bill = min(remaining_qty, receipt["remaining_qty"])
        remaining_qty = remaining_qty - qty_to_bill

        supplier_name = receipt["supplier"]
        
        if supplier_name not in supplier_items_map:
            supplier_items_map[supplier_name] = []
        
        # सप्लायर मैप में आइटम डेटा जोड़ें।
        supplier_items_map[supplier_name].append({
            "item_code": receipt["item_code"],
            "rate": receipt["rate"],
            "qty": qty_to_bill,
            "purchase_receipt": receipt["purchase_receipt"],
            "pr_detail": receipt["row_name"],
            "cost_center": doc.cost_center # Cost Center को आइटम रो पर सेट करना
        })

# --- Step 2: हर सप्लायर के लिए Purchase Invoices बनाएँ और सबमिट करें ---
for supplier, items in supplier_items_map.items():
    try:
        pi = frappe.new_doc("Purchase Invoice")
        pi.supplier = supplier
        
        # Purchase Invoice हेडर पर Cost Center सेट करना
        pi.cost_center = doc.cost_center 
        
        # VAT Taxes and Charges को कॉपी करना
        pi.taxes_and_charges = doc.taxes_and_charges
        
        for item_data in items:
            pi.append("items", item_data)
        
        pi.insert(ignore_permissions=True)
        pi.submit()

    except Exception as e:
        frappe.log_error(title=f"Error creating PI for {supplier}", message=str(e))

##################################### code 1 ######################################
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

######################################### code 2 ##########################################################
y dircet server script pr run krne k liye 
# Step 1: Initialize a map using a standard Python dictionary.
supplier_items_map = {} 

# Step 2: Sales Invoice ke har item ko check karte hain ki woh Consignment hai ya nahi
for item in doc.items:
    item_type = frappe.db.get_value("Item", item.item_code, "custom_item_type")
    
    if item_type != "Consignment":
        frappe.msgprint(f"Item {item.item_code} is not Consignment")
        continue

    # 3. Kitni quantity ko abhi bhi bill karna baaki hai
    remaining_qty = item.qty

    # 4. Iss item ke liye unbilled Purchase Receipts (PR) fetch karte hain
    receipts = frappe.db.sql("""
        SELECT 
            pri.parent AS purchase_receipt,  
            pri.rate,
            pri.item_code,
            pri.name as row_name,
            pr.supplier, 
            (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) AS remaining_qty 
        FROM `tabPurchase Receipt Item` AS pri
        JOIN `tabPurchase Receipt` AS pr
            ON pr.name = pri.parent
        WHERE pri.item_code = %s 
            AND pr.docstatus = 1
            AND (pri.qty - (pri.qty * IFNULL(pri.billed_amt, 0) / IFNULL(pri.net_amount, 1))) > 0
        ORDER BY pr.posting_date ASC
    """, (item.item_code,), as_dict=True)

    # 5. Har unbilled receipt par iterate karte hain
    for receipt in receipts:
        # 6. Agar required quantity puri bill ho chuki hai toh ruk jate hain
        if remaining_qty <= 0:
            break
        
        # Quantity calculate karte hain
        qty_to_bill = min(remaining_qty, receipt["remaining_qty"])
        remaining_qty = remaining_qty - qty_to_bill
        
        supplier_name = receipt["supplier"]

        # ********** FIX for KeyError **********
        # Pehle check karo ki supplier map mein hai ya nahi. Agar nahi hai, to list banao.
        if supplier_name not in supplier_items_map:
            supplier_items_map[supplier_name] = []
        # **************************************

        # Item ko list mein add karte hain
        supplier_items_map[supplier_name].append({
            "item_code": receipt["item_code"],
            "rate": receipt["rate"],
            "qty": qty_to_bill,
            "purchase_receipt": receipt["purchase_receipt"], 
            "pr_detail": receipt["row_name"]
        })

# Step 8: Ab har supplier ke liye ek Purchase Invoice (PI) banate hain
for supplier, items in supplier_items_map.items():
    pi = frappe.new_doc("Purchase Invoice")
    pi.supplier = supplier
    # set_posting_time ko hata diya gaya hai, taaki aap apni ERPNext setting ke hisaab se chalo.
    # Agar future mein time set karne ki zarurat ho to pi.set_posting_time = 1 wapas daal sakte ho.

    for item_data in items:
        pi.append("items", item_data)
    
    # Insert aur submit karte hain
    try:
        pi.insert()
        pi.submit()
        frappe.msgprint(f"Purchase Invoice {pi.name} created and submitted for Supplier {supplier}.")
    except Exception as e:
        # Simple logging taaki script fail na ho
        frappe.log_error(f"Failed to create/submit Purchase Invoice for Supplier {supplier}: {e}", "Consignment PI Create Error")
        frappe.msgprint(f"Error creating Purchase Invoice for Supplier {supplier}. Please check the Error Log.", title="Warning", indicator="red")


