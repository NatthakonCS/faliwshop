import streamlit as st
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps
from PIL import ImageDraw, ImageFont
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

import qrcode

# --- ฟังก์ชันสร้าง PromptPay Payload (Standard EMVCo) ---
def qrop(account_id, amount):
    # 1. จัดการเบอร์โทร (แปลง 08x -> 668x) หรือเลขบัตร
    target = str(account_id).replace("-", "").replace(" ", "").strip()
    if len(target) == 10 and target.startswith("0"): # เบอร์มือถือ
        target = "0066" + target[1:]
    
    # 2. สร้างโครงสร้างข้อมูล PromptPay (TLV)
    data = [
        "000201", "010211",
        f"29370016A000000677010111011300{target}",
        "5802TH", "5303764"
    ]
    
    # 3. ใส่จำนวนเงิน
    if amount:
        amt_str = f"{float(amount):.2f}"
        data.append(f"54{len(amt_str):02}{amt_str}")
    
    # 4. คำนวณ Checksum (CRC16) เพื่อความถูกต้องเป๊ะๆ
    raw_data = "".join(data) + "6304"
    crc = 0xFFFF
    for char in raw_data:
        crc ^= ord(char) << 8
        for _ in range(8):
            if (crc & 0x8000): crc = (crc << 1) ^ 0x1021
            else: crc <<= 1
    
    # คืนค่าเป็นรหัสพร้อมเพย์
    return raw_data + f"{crc & 0xFFFF:04X}"

# --- ฟังก์ชันสร้างใบเสร็จ (Receipt Generator) ---
def create_receipt_image(item_name, price, date_str, shop_name="HIGHCLASS"):
    width, height = 500, 800
    img = Image.new('RGB', (width, height), color='white')
    d = ImageDraw.Draw(img)
    
    # --- 1. ตั้งค่าฟอนต์ ---
    try:
        font_header = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_text = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24)
        font_price = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 50)
    except:
        font_header = ImageFont.load_default()
        font_text = ImageFont.load_default()
        font_price = ImageFont.load_default()

    # Helper function จัดกึ่งกลาง
    def draw_centered_text(y, text, font, fill="black"):
        bbox = d.textbbox((0, 0), text, font=font)
        text_width = bbox[2] - bbox[0]
        x = (width - text_width) // 2
        d.text((x, y), text, font=font, fill=fill)

    # --- 2. วาดข้อความ ---
    current_y = 50
    draw_centered_text(current_y, "RECEIPT", font_header)
    current_y += 60
    draw_centered_text(current_y, shop_name, font_text)
    
    current_y += 40
    d.line((50, current_y, width-50, current_y), fill="black", width=3)
    current_y += 40
    
    d.text((50, current_y), f"Date: {date_str}", font=font_text, fill="black")
    current_y += 50
    d.text((50, current_y), f"Item: {item_name}", font=font_text, fill="black")
    current_y += 80
    
    draw_centered_text(current_y, "TOTAL AMOUNT", font_text)
    current_y += 50
    draw_centered_text(current_y, f"{price:,.0f} THB", font_price)
    
    current_y += 80
    d.line((50, current_y, width-50, current_y), fill="black", width=3)
    current_y += 40
    
    # ... (ส่วนวาด Text ด้านบนเหมือนเดิม) ...
    
    # --- 3. สร้าง QR Code (ฉบับชัดเป๊ะ สแกนติดชัวร์) ---
    my_promptpay_id = "0812345678" # 👈 เช็กอีกทีว่าแก้เบอร์หรือยังนะครับ!
    
    # 1. เรียกฟังก์ชันสร้างรหัส
    payload = qrop(my_promptpay_id, price)
    
    # 2. ตั้งค่า QR Code ให้มีความละเอียดสูง + มีขอบขาว
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L, # ความละเอียด L สแกนง่ายสุด
        box_size=10, # ขนาดจุดใหญ่ขึ้น
        border=2     # 👈 สำคัญ! ต้องมีขอบขาวอย่างน้อย 2-4 หน่วย
    )
    qr.add_data(payload)
    qr.make(fit=True)
    
    # 3. สร้างรูป QR (ขาว-ดำ ชัดๆ)
    qr_img = qr.make_image(fill_color="black", back_color="white")
    
    # 4. ย่อขนาดลงหน่อยให้พอดีใบเสร็จ (แต่ยังชัดอยู่)
    qr_img = qr_img.resize((250, 250))
    
    # 5. แปะลงกระดาษ
    qr_x = (width - 250) // 2
    img.paste(qr_img, (qr_x, current_y))
    
    # ... (ส่วน Thank You ด้านล่างเหมือนเดิม) ...
    

    
    return img

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="HIGHCLASS", layout="wide")

# --- 🔐 SYSTEM: LOGIN (วางต่อจาก st.set_page_config) ---
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

def check_login():
    st.markdown("""
        <style>
            .stTextInput input { text-align: center; }
            div[data-testid="stForm"] { 
                border: 2px solid #FF4B4B; 
                border-radius: 20px; 
                padding: 30px; 
                box-shadow: 0 4px 15px rgba(0,0,0,0.2);
            }
        </style>
    """, unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.markdown("<h2 style='text-align: center;'>🔐 HIGHCLASS SHOP</h2>", unsafe_allow_html=True)
        with st.form("login_form"):
            user = st.text_input("Username", placeholder="User")
            pwd = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("LOGIN", use_container_width=True, type="primary")
            
            if submitted:
                # ดึงรหัสลับมาจาก Secrets (ตู้เซฟ) โดยตรง
                correct_user = st.secrets["credentials"]["username"]
                correct_pass = st.secrets["credentials"]["password"]
                
                if user == correct_user and pwd == correct_pass:
                    st.session_state.logged_in = True
                    st.toast("Welcome back, Boss! 😎")
                    st.rerun()
                else:
                    st.error("❌ Access Denied!")

if not st.session_state.logged_in:
    check_login()
    st.stop() # 🛑 สั่งหยุด! ห้ามรันโค้ดบรรทัดล่างถ้ายังไม่ล็อกอิน

# --- 👇 โค้ดร้านค้าของเดิม เริ่มทำงานต่อจากตรงนี้ 👇 ---


# 🟢 ใส่ URL Google Sheets ของฟิวตรงนี้
SHEET_URL = "https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing"

# เชื่อมต่อ
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    footer {visibility: hidden;}
    .stButton>button { border-radius: 12px; font-weight: 600; }
    div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
</style>
""", unsafe_allow_html=True)

# --- Helper Functions (ระบบแปลงไฟล์รูป) ---

def get_data(worksheet_name):
    try:
        # ttl=0 เพื่อให้ดึงข้อมูลใหม่เสมอ
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
        return df
    except Exception:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=df)

def image_to_base64(pil_img):
    """แปลงรูปภาพเป็นตัวหนังสือ Base64 เพื่อเก็บใน Google Sheets"""
    pil_img = pil_img.convert('RGB')
    pil_img.thumbnail((300, 300)) # ย่อรูปให้เบา
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG", quality=80)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# --- Sidebar ---
with st.sidebar:
    st.markdown("## 🛍️ HIGHCLASS SHOP")
    selected = option_menu(
        menu_title=None,
        # เพิ่ม "Sold Items" เข้าไปใน options และ icons
        options=["Dashboard", "Transactions", "Inventory", "Sold Items"],
        icons=["grid-1x2", "wallet", "box-seam-fill", "bag-check-fill"], 
        default_index=0,
    )

# --- Load Data ---
df_trans = get_data("transactions")
df_prod = get_data("products")

# สร้างหัวตารางถ้าย้อนกลับมาแล้วว่างเปล่า
if df_trans.empty:
    df_trans = pd.DataFrame(columns=['date', 'type', 'title', 'amount'])
if df_prod.empty:
    df_prod = pd.DataFrame(columns=['product_id', 'name', 'image_base64', 'sell_price', 'discount_price', 'cost_price', 'status', 'actual_sold_price', 'sold_date'])

# === PAGE: DASHBOARD ===
if selected == "Dashboard":
    st.markdown("### 👋 Overview")
    
    # 1. ดึงข้อมูลรายรับ-รายจ่ายทั่วไป (ค่าน้ำ, ค่าไฟ, ทุนก้อนแรก)
    if not df_trans.empty:
        inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum()
        exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum()
    else: inc, exp = 0, 0

    # 2. คำนวณกระแสเงินสดจากสินค้า (เสื้อผ้า)
    if not df_prod.empty:
        # เงินเข้า (Revenue): ได้จากเสื้อตัวที่ขายออกไปแล้ว
        sold_items = df_prod[df_prod['status']=='Sold']
        total_revenue = sold_items['actual_sold_price'].sum()
        
        # เงินออก (Cost of Inventory): คือเงินที่จ่ายไปซื้อเสื้อ "ทุกตัว" (ทั้งที่ขายแล้วและยังอยู่)
        # นี่คือจุดสำคัญ! ระบบจะหักเงินทุนทันทีที่เรา Add Item เข้าไป
        total_stock_cost = df_prod['cost_price'].sum()
        
        # มูลค่าสินค้าที่ยังกองอยู่หลังร้าน (Asset)
        stock_val = df_prod[df_prod['status']=='Available']['cost_price'].sum()
        
        # กำไรเฉพาะตัวเสื้อผ้า (ขายได้ - ทุนของตัวที่ขาย)
        profit_clothes = total_revenue - sold_items['cost_price'].sum()
        sold_count = len(sold_items)
    else: 
        total_revenue, total_stock_cost, stock_val, profit_clothes, sold_count = 0, 0, 0, 0, 0

    # 3. สรุปเงินสดคงเหลือ (Real Cash Balance)
    # สูตร: (เงินทุนก้อนแรก + เงินที่ขายเสื้อได้) - (ค่าใช้จ่ายทั่วไป + เงินที่จ่ายค่าเสื้อไปทั้งหมด)
    net_cash = (inc + total_revenue) - (exp + total_stock_cost)

    col1, col2, col3 = st.columns(3)
    col1.metric("✨ Net Profit (Clothes)", f"฿ {profit_clothes:,.0f}", f"{sold_count} items sold")
    col2.metric("💵 Cash Balance", f"฿ {net_cash:,.0f}")
    col3.metric("📦 Stock Value (Asset)", f"฿ {stock_val:,.0f}")


    # === PAGE: TRANSACTIONS ===
elif selected == "Transactions":
    st.markdown("### 💸 Income & Expenses")
    with st.form("trans_form", clear_on_submit=True):
        c1, c2, c3, c4 = st.columns([2, 2, 4, 2])
        d_date = c1.date_input("Date", datetime.now())
        d_type = c2.selectbox("Type", ["รายจ่าย", "รายรับ"])
        d_title = c3.text_input("Title")
        d_amt = c4.number_input("Amount", min_value=0.0)
        if st.form_submit_button("Add Entry", type="primary"):
            new_row = pd.DataFrame([{'date': str(d_date), 'type': d_type, 'title': d_title, 'amount': d_amt}])
            updated_df = pd.concat([df_trans, new_row], ignore_index=True)
            save_data(updated_df, "transactions")
            st.toast("Saved!")
            st.rerun()

    if not df_trans.empty:
        st.dataframe(df_trans.sort_index(ascending=False), use_container_width=True, hide_index=True)

    # === PAGE: INVENTORY ===
elif selected == "Inventory":
    st.markdown("### 👕 Stock Management")
    
    # --- 🧾 แก้ไข: สร้างฟังก์ชันโชว์ใบเสร็จ (ต้องเขียนแบบนี้) ---
    @st.dialog("🧾 Payment Receipt")
    def show_receipt_modal():
        st.image(st.session_state['last_receipt'], caption="Save รูปนี้ส่งให้ลูกค้าได้เลยครับ", use_container_width=True)
        
        # แปลงรูปเพื่อเตรียมดาวน์โหลด
        buf = BytesIO()
        st.session_state['last_receipt'].save(buf, format="JPEG")
        byte_im = buf.getvalue()
        
        col1, col2 = st.columns(2)
        # ปุ่มดาวน์โหลด
        col1.download_button(
            label="⬇️ Download",
            data=byte_im,
            file_name=st.session_state['last_receipt_name'],
            mime="image/jpeg",
            type="primary"
        )
        # ปุ่มปิด
        if col2.button("Close"):
            del st.session_state['last_receipt'] # ลบใบเสร็จออกจากความจำ
            st.rerun()

    # เรียกใช้ฟังก์ชันด้านบน ถ้ามีใบเสร็จค้างอยู่
    if 'last_receipt' in st.session_state:
        show_receipt_modal()
    # ----------------------------------------

    # ... (ส่วน Tab ข้างล่างปล่อยไว้เหมือนเดิม ไม่ต้องแก้) ...
    tab_sell, tab_add, tab_hist = st.tabs(["🛍️ Shop", "➕ Add Item", "📊 Sales Log"])
    
    # --- TAB: SHOP ---
    with tab_sell:
        if 'category' not in df_prod.columns:
            df_prod['category'] = 'Uncategorized'
            
        all_cats = ["All"] + sorted(df_prod[df_prod['status']=='Available']['category'].astype(str).unique().tolist())
        
        c_search, c_filter = st.columns([2, 1])
        q = c_search.text_input("Search", placeholder="🔍 ID or Name...", label_visibility="collapsed")
        cat_filter = c_filter.selectbox("📂 Filter by Category", all_cats, label_visibility="collapsed")

        if not df_prod.empty:
            items = df_prod[df_prod['status'] == 'Available']
            
            if cat_filter != "All":
                items = items[items['category'] == cat_filter]

            if q:
                mask = items['product_id'].astype(str).str.contains(q, case=False) | items['name'].str.contains(q, case=False)
                items = items[mask]

            if items.empty: 
                st.info(f"ไม่พบสินค้า")
            
            # Loop แสดงสินค้า
            for i in range(0, len(items), 2):
                cols = st.columns(2)
                for idx, row in enumerate(items.iloc[i:i+2].itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            # รูปภาพ
                            if pd.notna(row.image_base64) and str(row.image_base64).startswith('data:image'):
                                st.image(row.image_base64, use_container_width=True)
                            else:
                                st.markdown("*(No Image)*")
                            
                            st.markdown(f"**{row.name}**")
                            st.caption(f"📂 {row.category} | ID: {row.product_id}")
                            
                            c1, c2 = st.columns(2)
                            c1.markdown(f"🏷️ Sell: **{row.sell_price:,.0f}**")
                            c2.markdown(f"📉 Floor: <span style='color:red'>{row.discount_price:,.0f}</span>", unsafe_allow_html=True)
                            st.markdown(f"🏭 Cost: `{row.cost_price:,.0f}`")
                            
                            # ปุ่มควบคุม
                            unique_key_suffix = f"{row.product_id}_{row.Index}"
                            b_sell, b_edit = st.columns(2)
                            
                            # --- ปุ่มที่ 1: ขาย (SELL) พร้อมใบเสร็จ ---
                            with b_sell:
                                with st.popover("⚡ Sell", use_container_width=True):
                                    st.markdown(f"Selling: **{row.name}**")
                                    actual_p = st.number_input("Price", value=float(row.sell_price), key=f"p_{unique_key_suffix}")
                                    
                                    if actual_p < row.cost_price: st.warning("⚠️ ขาดทุน!")
                                    elif actual_p < row.discount_price: st.warning("⚠️ ต่ำกว่า Floor!")

                                    # จุดที่เคย Error คือตรงนี้ครับ (ตอนนี้แก้ให้แล้ว)
                                    if st.button("Confirm", key=f"b_sell_{unique_key_suffix}", type="primary"):
                                        # 1. บันทึก
                                        df_prod.loc[row.Index, ['status','actual_sold_price','sold_date']] = ['Sold', actual_p, str(datetime.now())]
                                        save_data(df_prod, "products")
                                        
                                        # 2. สร้างใบเสร็จ
                                        receipt_img = create_receipt_image(
                                            item_name=row.name,
                                            price=actual_p,
                                            date_str=datetime.now().strftime("%Y-%m-%d %H:%M")
                                        )
                                        
                                        # 3. เก็บใบเสร็จเพื่อโชว์
                                        st.session_state['last_receipt'] = receipt_img
                                        st.session_state['last_receipt_name'] = f"Receipt_{row.name}.jpg"
                                        
                                        st.toast(f"Sold {row.name}!")
                                        st.rerun()

                            # --- ปุ่มที่ 2: แก้ไข (EDIT) ---
                            with b_edit:
                                with st.popover("✏️ Edit", use_container_width=True):
                                    st.markdown(f"**Edit: {row.name}**")
                                    with st.form(key=f"edit_form_{unique_key_suffix}"):
                                        e_name = st.text_input("Name", value=row.name)
                                        e_cat = st.text_input("Category", value=row.category)
                                        
                                        ec1, ec2, ec3 = st.columns(3)
                                        e_cost = ec1.number_input("Cost", value=float(row.cost_price))
                                        e_sell = ec2.number_input("Sell", value=float(row.sell_price))
                                        e_floor = ec3.number_input("Floor", value=float(row.discount_price))
                                        e_img = st.file_uploader("Change Image", type=['png','jpg','jpeg'])
                                        
                                        if st.form_submit_button("Save Changes"):
                                            df_prod.at[row.Index, 'name'] = e_name
                                            df_prod.at[row.Index, 'category'] = e_cat
                                            df_prod.at[row.Index, 'cost_price'] = e_cost
                                            df_prod.at[row.Index, 'sell_price'] = e_sell
                                            df_prod.at[row.Index, 'discount_price'] = e_floor
                                            
                                            if e_img:
                                                new_image = Image.open(e_img)
                                                new_image = ImageOps.exif_transpose(new_image)
                                                df_prod.at[row.Index, 'image_base64'] = image_to_base64(new_image)
                                            
                                            save_data(df_prod, "products")
                                            st.success("Updated!")
                                            st.rerun()
        else:
            st.info("Stock is empty.")
    
    # --- TAB: ADD ITEM ---
    with tab_add:
        uploaded_file = st.file_uploader("Upload Image", type=['png','jpg','jpeg'])
        if uploaded_file:
            image = Image.open(uploaded_file)
            image = ImageOps.exif_transpose(image)
            st.image(image, caption="Preview", width=200)

        with st.form("add_prod", clear_on_submit=True):
            c1, c2 = st.columns(2)
            nid = c1.text_input("ID")
            nname = c2.text_input("Name")
            c3, c4 = st.columns(2)
            ncat = c3.text_input("Category / Brand", placeholder="e.g. Nike, Polo") 
            ncost = c4.number_input("Cost (ทุน)", min_value=0.0)
            c5, c6 = st.columns(2)
            nprice = c5.number_input("Sell Price (ขาย)", min_value=0.0)
            nfloor = c6.number_input("Floor Price (ต่ำสุด)", min_value=0.0)
            
            if st.form_submit_button("Save Item", type="primary"):
                if nid and nname and uploaded_file:
                    img_str = image_to_base64(image)
                    final_cat = ncat if ncat else "General" 
                    new_item = pd.DataFrame([{
                        'product_id': nid, 'name': nname, 'category': final_cat, 'image_base64': img_str,
                        'sell_price': nprice, 'discount_price': nfloor, 'cost_price': ncost,
                        'status': 'Available', 'actual_sold_price': 0, 'sold_date': None
                    }])
                    updated_stock = pd.concat([df_prod, new_item], ignore_index=True)
                    save_data(updated_stock, "products")
                    st.success(f"Added {nname}!")
                    st.rerun()
                else:
                    st.error("Please fill all fields & upload image.")

    # --- TAB: HISTORY ---
    with tab_hist:
        if not df_prod.empty:
            sold_items = df_prod[df_prod['status']=='Sold']
            if not sold_items.empty:
                sold_items['profit'] = sold_items['actual_sold_price'] - sold_items['cost_price']
                st.dataframe(sold_items[['sold_date','name','category','actual_sold_price','profit']], use_container_width=True, hide_index=True)
            else:
                st.caption("No sales yet.")
                
# === PAGE: SOLD ITEMS (เพิ่มระบบดึงของกลับ) ===
elif selected == "Sold Items":
    st.markdown("### ✅ Sold Out Gallery")
    
    # กรองเฉพาะสินค้าที่ขายแล้ว
    if not df_prod.empty:
        sold_items = df_prod[df_prod['status'] == 'Sold']
        
        # เรียงจากขายล่าสุดก่อน
        if 'sold_date' in sold_items.columns:
            sold_items = sold_items.sort_values(by='sold_date', ascending=False)

        if sold_items.empty:
            st.info("ยังไม่มีสินค้าที่ขายออกไป สู้ๆ ครับ! ✌️")
        else:
            # สรุปยอดรวม
            total_rev = sold_items['actual_sold_price'].sum()
            total_profit = total_rev - sold_items['cost_price'].sum()
            st.metric("🎉 Total Sales Volume", f"฿ {total_rev:,.0f}", f"Profit: ฿ {total_profit:,.0f}")
            st.divider()

            # Loop แสดงสินค้า
            for i in range(0, len(sold_items), 2):
                cols = st.columns(2)
                for idx, row in enumerate(sold_items.iloc[i:i+2].itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            # รูปภาพ
                            if pd.notna(row.image_base64) and str(row.image_base64).startswith('data:image'):
                                st.image(row.image_base64, use_container_width=True)
                            else:
                                st.markdown("*(No Image)*")
                            
                            st.markdown(f"**{row.name}**")
                            
                            # เช็กว่ามีคอลัมน์ category ไหม (กัน Error)
                            cat_show = row.category if 'category' in df_prod.columns else '-'
                            st.caption(f"ID: {row.product_id} | 📂 {cat_show}")
                            
                            # ข้อมูลการขาย
                            c1, c2 = st.columns(2)
                            c1.markdown(f"💰 Sold: **{row.actual_sold_price:,.0f}**")
                            
                            profit = row.actual_sold_price - row.cost_price
                            if profit > 0:
                                c2.markdown(f"🔥 <span style='color:green'>+{profit:,.0f}</span>", unsafe_allow_html=True)
                            else:
                                c2.markdown(f"🔻 <span style='color:red'>{profit:,.0f}</span>", unsafe_allow_html=True)
                            
                            st.caption(f"📅 {str(row.sold_date)[:16]}")
                            
                            # --- 🛠️ ส่วนที่เพิ่มใหม่: ปุ่มดึงของกลับ ---
                            unique_key_sold = f"restore_{row.product_id}_{row.Index}"
                            
                            with st.popover("❌ Cancel / Restock", use_container_width=True):
                                st.markdown(f"ดึง **{row.name}** กลับไปขายใหม่?")
                                st.caption("⚠️ สินค้าจะกลับไปหน้า Shop และลบยอดขายนี้ออก")
                                
                                if st.button("ยืนยันดึงของกลับ", key=unique_key_sold, type="primary"):
                                    # 1. แก้สถานะกลับเป็น Available
                                    df_prod.at[row.Index, 'status'] = 'Available'
                                    # 2. ล้างข้อมูลการขายทิ้ง
                                    df_prod.at[row.Index, 'actual_sold_price'] = 0
                                    df_prod.at[row.Index, 'sold_date'] = None
                                    
                                    # 3. บันทึกและรีเฟรช
                                    save_data(df_prod, "products")
                                    st.toast(f"Restored {row.name} to Shop!")
                                    st.rerun()
    else:
        st.info("No data available.")
