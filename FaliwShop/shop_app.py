
import streamlit as st
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps

from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

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
            # ... (ต่อจากบรรทัด if items.empty: st.info("ไม่พบสินค้า")) ...

            # Loop แสดงสินค้า (ฉบับแก้ปุ่มซ้ำ)
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
                            
                            # --- ส่วนปุ่มควบคุม (แก้ใหม่ตรงนี้) ---
                            unique_key_suffix = f"{row.product_id}_{row.Index}"
                            
                            # แบ่งเป็น 3 ปุ่ม: ขาย (2ส่วน), ก๊อปปี้ (1ส่วน), แก้ไข (1ส่วน)
                            b_sell, b_cap, b_edit = st.columns([2, 1, 1])
                            
                            # 1. ปุ่มขาย (SELL)
                            with b_sell:
                                with st.popover("⚡ Sell", use_container_width=True):
                                    st.markdown(f"Selling: **{row.name}**")
                                    actual_p = st.number_input("Price", value=float(row.sell_price), key=f"p_{unique_key_suffix}")
                                    
                                    if actual_p < row.cost_price: st.warning("⚠️ ขาดทุน!")
                                    elif actual_p < row.discount_price: st.warning("⚠️ ต่ำกว่า Floor!")

                                    if st.button("Confirm", key=f"b_sell_{unique_key_suffix}", type="primary"):
                                        df_prod.loc[row.Index, ['status','actual_sold_price','sold_date']] = ['Sold', actual_p, str(datetime.now())]
                                        save_data(df_prod, "products")
                                        st.toast(f"Sold {row.name}!")
                                        st.rerun()

                            # 2. ปุ่มแคปชั่น (COPY)
                            with b_cap:
                                with st.popover("📋", use_container_width=True):
                                    st.markdown("##### 📝 Copy Caption")
                                    st.caption("กดปุ่ม Copy มุมขวาบน 👇")
                                    
                                    # สร้างข้อความ
                                    caption_txt = f"""🔥 {row.name}
📂 Brand: {row.category}
💵 Price: {row.sell_price:,.0f}.-

📏 Size: (ระบุไซส์) / ยาว (ระบุ)
✨ Condition: 9.5/10 (ซักรีดหอมพร้อมใส่)
__________________________
🚚 ค่าส่ง 50.- (พื้นที่ห่างไกล +20)
📩 สนใจทัก DM หรือพิมพ์จองได้เลยครับ

#HighClass #{str(row.category).replace(" ", "")} #เสื้อผ้ามือสอง #VintageStyle"""
                                    
                            st.code(caption_txt, language="markdown")

                            # 3. ปุ่มแก้ไข (EDIT)
                            with b_edit:
                                with st.popover("✏️", use_container_width=True):
                                    st.markdown(f"**Edit: {row.name}**")
                                    # เช็กตรงนี้: key ต้องไม่ซ้ำ
                                    with st.form(key=f"edit_form_{unique_key_suffix}"):
                                        e_name = st.text_input("Name", value=row.name)
                                        e_cat = st.text_input("Category", value=row.category)
                                        ec1, ec2, ec3 = st.columns(3)
                                        e_cost = ec1.number_input("Cost", value=float(row.cost_price))
                                        e_sell = ec2.number_input("Sell", value=float(row.sell_price))
                                        e_floor = ec3.number_input("Floor", value=float(row.discount_price))
                                        e_img = st.file_uploader("Change Image", type=['png','jpg','jpeg'])
                                        
                                        if st.form_submit_button("Save"):
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

                            # --- 2. ปุ่มแคปชั่น (CAPTION) [ใหม่! ✨] ---
                            with b_cap:
                                with st.popover("📋", use_container_width=True):
                                    st.markdown("##### 📝 Copy Caption")
                                    st.caption("กดปุ่ม Copy มุมขวาบนได้เลย 👇")
                                    
                                    # สร้างข้อความอัตโนมัติ
caption_txt = f"""🔥 {row.name}
📂 Brand: {row.category}
💵 Price: {row.sell_price:,.0f}.-
                                    
📏 Size: (ระบุไซส์) / ยาว (ระบุ)
✨ Condition: 9.5/10 (ซักรีดหอมพร้อมใส่)
__________________________
🚚 ค่าส่ง 50.- (พื้นที่ห่างไกล +20)
📩 สนใจทัก DM หรือพิมพ์จองได้เลยครับ
                                    
#HighClass #{row.category.replace(" ", "")} #เสื้อผ้ามือสอง #VintageStyle"""
                                    
                                    # แสดงเป็นกล่อง Code (มันจะมีปุ่ม Copy ให้เองอัตโนมัติ!)
                                    st.code(caption_txt, language="markdown")

                            # --- 3. ปุ่มแก้ไข (EDIT) ---
                            with b_edit:
                                with st.popover("✏️", use_container_width=True):
                                    st.markdown(f"**Edit: {row.name}**")
                                    with st.form(key=f"edit_form_{unique_key_suffix}"):
                                        e_name = st.text_input("Name", value=row.name)
                                        e_cat = st.text_input("Category", value=row.category)
                                        ec1, ec2, ec3 = st.columns(3)
                                        e_cost = ec1.number_input("Cost", value=float(row.cost_price))
                                        e_sell = ec2.number_input("Sell", value=float(row.sell_price))
                                        e_floor = ec3.number_input("Floor", value=float(row.discount_price))
                                        
                                        if st.form_submit_button("Save"):
                                            df_prod.at[row.Index, 'name'] = e_name
                                            df_prod.at[row.Index, 'category'] = e_cat
                                            df_prod.at[row.Index, 'cost_price'] = e_cost
                                            df_prod.at[row.Index, 'sell_price'] = e_sell
                                            df_prod.at[row.Index, 'discount_price'] = e_floor
                                            save_data(df_prod, "products")
                                            st.success("Updated!")
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
