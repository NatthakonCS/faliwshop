import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image, ImageOps
from streamlit_option_menu import option_menu
import io
from streamlit_gsheets import GSheetsConnection

# 1. สร้างการเชื่อมต่อ
conn = st.connection("gsheets", type=GSheetsConnection)

# 2. วิธีอ่านข้อมูล (แทน SQL SELECT)
data = conn.read(spreadsheet="https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing", worksheet="ชีต1")

# 3. วิธีเพิ่มข้อมูล (แทน SQL INSERT)
# สมมติฟิวมี DataFrame ใหม่ชื่อ new_data
# updated_df = pd.concat([data, new_data], ignore_index=True)
# conn.update(spreadsheet="URL_ของ_GOOGLE_SHEET_ฟิว", data=updated_df)

# --- 1. Setup หน้าเว็บ ---
st.set_page_config(page_title="Shop Manager", layout="wide")

# CSS Customization
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    footer {visibility: hidden;}
    
    /* ปุ่มกด Modern */
    .stButton>button {
        border-radius: 12px; font-weight: 600; border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2); transition: all 0.2s;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
    
    /* Card สินค้า */
    div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    /* Input & Header */
    .stTextInput>div>div>input { border-radius: 10px; }
    header[data-testid="stHeader"] { background-color: transparent; }
</style>
""", unsafe_allow_html=True)

IMAGE_FOLDER = 'product_images'
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# --- Database ---
def init_db():
    conn = sqlite3.connect('myshop.db')
    c = conn.cursor()
    c.execute('CREATE TABLE IF NOT EXISTS transactions (id INTEGER PRIMARY KEY, date TEXT, type TEXT, title TEXT, amount REAL)')
    c.execute('CREATE TABLE IF NOT EXISTS products (product_id TEXT PRIMARY KEY, name TEXT, image_path TEXT, sell_price REAL, discount_price REAL, cost_price REAL, status TEXT, actual_sold_price REAL, sold_date TEXT)')
    conn.commit()
    return conn

conn = init_db()

# --- Image Processing Functions (New!) ---
def make_square_and_resize(pil_img, target_size=800):
    """ทำให้ภาพเป็นสี่เหลี่ยมจัตุรัสโดยการเติมขอบขาว และย่อขนาด"""
    # แปลงเป็น RGB เผื่อเป็น PNG โปร่งใส
    pil_img = pil_img.convert('RGB')
    width, height = pil_img.size
    
    # หาด้านที่ยาวที่สุด
    max_side = max(width, height)
    
    # สร้างภาพพื้นหลังสีขาวสี่เหลี่ยมจัตุรัส
    new_img = Image.new('RGB', (max_side, max_side), (255, 255, 255))
    
    # แปะภาพเดิมลงตรงกลาง
    offset = ((max_side - width) // 2, (max_side - height) // 2)
    new_img.paste(pil_img, offset)
    
    # ย่อขนาดลงมาให้พอดี (ถ้าภาพใหญ่เกินไป)
    if max_side > target_size:
        new_img = new_img.resize((target_size, target_size), Image.LANCZOS)
        
    return new_img

def save_processed_image(pil_img, product_id):
    """บันทึกภาพ PIL ลงเครื่อง"""
    filename = f"{product_id}.jpg" # บันทึกเป็น JPG เสมอ
    filepath = os.path.join(IMAGE_FOLDER, filename)
    # save สภาพปัจจุบัน (ที่หมุนแล้ว)
    pil_img.save(filepath, 'JPEG', quality=90)
    return filepath

# --- 2. Sidebar Menu ---
with st.sidebar:
    st.markdown("""
        <h1 style='text-align: center; background: -webkit-linear-gradient(45deg, #FF512F, #DD2476); -webkit-background-clip: text; -webkit-text-fill-color: transparent; font-weight: 800;'>
            FALIW SHOP
        </h1>
    """, unsafe_allow_html=True)
    
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Transactions", "Inventory"],
        icons=["grid-1x2", "wallet", "box-seam-fill"], 
        default_index=2, # ตั้งค่าเริ่มต้นที่หน้า Inventory เพื่อทดสอบง่ายๆ
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#888", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "border-radius": "10px"},
            "nav-link-selected": {"background-color": "#FF512F", "color": "white", "font-weight": "600"},
        }
    )

# --- 3. Content ---

# === PAGE: DASHBOARD ===
if selected == "Dashboard":
    st.markdown("### 👋 Overview")
    df_trans = pd.read_sql("SELECT * FROM transactions", conn)
    df_prod = pd.read_sql("SELECT * FROM products", conn)
    inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum()
    exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum()
    sold = df_prod[df_prod['status']=='Sold']
    rev_clothes = sold['actual_sold_price'].sum()
    cost_clothes = sold['cost_price'].sum()
    profit_clothes = rev_clothes - cost_clothes
    stock_val = df_prod[df_prod['status']=='Available']['cost_price'].sum()
    net = (inc + rev_clothes) - (exp + cost_clothes)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("✨ Net Profit (Clothes)", f"฿ {profit_clothes:,.0f}", f"{len(sold)} items sold")
    with col2:
        with st.container(border=True):
            st.metric("💵 Cash Balance", f"฿ {net:,.0f}")
    with col3:
        with st.container(border=True):
            st.metric("📦 Stock Value", f"฿ {stock_val:,.0f}", delta_color="off")

# === PAGE: TRANSACTIONS ===
elif selected == "Transactions":
    st.markdown("### 💸 Income & Expenses")
    with st.container(border=True):
        st.markdown("**New Entry**")
        c_date, c_type, c_title, c_amt, c_btn = st.columns([2, 2, 4, 2, 2])
        d_date = c_date.date_input("Date", datetime.now(), label_visibility="collapsed")
        d_type = c_type.selectbox("Type", ["รายจ่าย", "รายรับ"], label_visibility="collapsed")
        d_title = c_title.text_input("Title", placeholder="Description...", label_visibility="collapsed")
        d_amt = c_amt.number_input("Amount", min_value=0.0, label_visibility="collapsed", placeholder="0.00")
        if c_btn.button("Add", use_container_width=True, type="primary"):
            if d_title and d_amt > 0:
                conn.execute("INSERT INTO transactions (date, type, title, amount) VALUES (?,?,?,?)", (d_date, d_type, d_title, d_amt))
                conn.commit()
                st.toast("Saved successfully!")
                st.rerun()
    st.markdown("#### 📜 History")
    df = pd.read_sql("SELECT date, type, title, amount FROM transactions ORDER BY id DESC LIMIT 10", conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

# === PAGE: INVENTORY ===
elif selected == "Inventory":
    st.markdown("### 👕 Stock Management")
    tab_sell, tab_add, tab_hist = st.tabs(["🛍️ Shop", "➕ Add Item (New!)", "📊 Sales Log"])
    
    # --- TAB: SHOP ---
    with tab_sell:
        col_search, _ = st.columns([3, 1])
        q = col_search.text_input("Search", placeholder="🔍 Find by ID or Name...", label_visibility="collapsed")
        sql = "SELECT * FROM products WHERE status = 'Available'"
        params = []
        if q:
            sql += " AND (product_id LIKE ? OR name LIKE ?)"
            params = [f"%{q}%", f"%{q}%"]
        df = pd.read_sql(sql, conn, params=params)
        if df.empty:
            st.caption("No items found.")
        else:
            # แสดงผลแบบ Grid
            for i in range(0, len(df), 2):
                cols = st.columns(2)
                batch = df.iloc[i:i+2]
                for idx, row in enumerate(batch.itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            # แสดงรูปภาพ (ซึ่งตอนนี้ถูกบังคับเป็นสี่เหลี่ยมจัตุรัสแล้ว)
                            if row.image_path and os.path.exists(row.image_path):
                                st.image(row.image_path, use_container_width=True)
                            
                            st.markdown(f"**{row.name}**")
                            st.caption(f"ID: {row.product_id}")
                            c1, c2 = st.columns(2)
                            c1.markdown(f"🏷️ **{row.sell_price:,.0f}**")
                            c2.markdown(f"🔒 Floor: {row.discount_price:,.0f}")
                            
                            b_sell, b_del = st.columns([4, 1])
                            with b_sell:
                                with st.popover("⚡ Sell", use_container_width=True):
                                    st.markdown(f"Selling: **{row.name}**")
                                    actual_p = st.number_input("Sold Price", value=row.sell_price, key=f"p_{row.product_id}")
                                    if actual_p < row.discount_price: st.caption("⚠️ Below floor price!")
                                    if st.button("Confirm Sale", key=f"b_{row.product_id}", type="primary"):
                                        conn.execute('UPDATE products SET status="Sold", actual_sold_price=?, sold_date=? WHERE product_id=?', (actual_p, datetime.now(), row.product_id))
                                        conn.commit()
                                        st.rerun()
                            with b_del:
                                with st.popover("🗑️", use_container_width=True):
                                    st.markdown(f"⚠️ **Delete** {row.name}?")
                                    if st.button("Yes", key=f"del_{row.product_id}", type="primary"):
                                        conn.execute("DELETE FROM products WHERE product_id = ?", (row.product_id,))
                                        conn.commit()
                                        if row.image_path and os.path.exists(row.image_path):
                                            try: os.remove(row.image_path)
                                            except: pass
                                        st.toast(f"Deleted {row.name}!")
                                        st.rerun()

    # --- TAB: ADD ITEM (ระบบใหม่: หมุน + จัดขนาด) ---
    with tab_add:
        with st.container(border=True):
            st.markdown("#### 1️⃣ Upload & Rotate Image")
            
            # 1. อัปโหลดไฟล์
            uploaded_file = st.file_uploader("Choose Image", type=['png','jpg','jpeg'], label_visibility="collapsed")
            
            # Session State สำหรับเก็บรูปภาพที่กำลังแก้ไข
            if 'current_image' not in st.session_state:
                st.session_state.current_image = None
            if 'last_uploaded_file' not in st.session_state:
                st.session_state.last_uploaded_file = None

            # ถ้ามีการอัปโหลดไฟล์ใหม่ ให้โหลดเข้า Session State
            if uploaded_file is not None and uploaded_file != st.session_state.last_uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    # แก้ปัญหา Orientation ของภาพจากมือถือบางรุ่น
                    image = ImageOps.exif_transpose(image) 
                    st.session_state.current_image = image
                    st.session_state.last_uploaded_file = uploaded_file
                except:
                    st.error("ไฟล์รูปภาพมีปัญหา")

            # ถ้ามีรูปในระบบ ให้แสดงตัวอย่างและปุ่มหมุน
            rotated_image_ready_to_save = None
            if st.session_state.current_image is not None:
                col_prev, col_rot = st.columns([2, 1], gap="medium")
                with col_prev:
                    # แสดงตัวอย่างรูปปัจจุบัน
                    st.image(st.session_state.current_image, caption="Preview", use_container_width=True)
                with col_rot:
                    st.markdown("Change Orientation:")
                    # ปุ่มหมุน
                    if st.button("🔄 หมุนซ้าย (90°)", use_container_width=True):
                        st.session_state.current_image = st.session_state.current_image.rotate(90, expand=True)
                        st.rerun() # รีเฟรชหน้าเพื่อแสดงภาพใหม่
                    if st.button("🔃 หมุนขวา (90°)", use_container_width=True):
                        st.session_state.current_image = st.session_state.current_image.rotate(-90, expand=True)
                        st.rerun()
                
                rotated_image_ready_to_save = st.session_state.current_image
                st.divider()

            # 2. ฟอร์มกรอกข้อมูล
            st.markdown("#### 2️⃣ Product Details")
            with st.form("add_prod_form", clear_on_submit=True): # ใช้ clear_on_submit เพื่อเคลียร์ช่องข้อความ
                c_dat1, c_dat2 = st.columns(2)
                nid = c_dat1.text_input("ID (ห้ามซ้ำ)")
                nname = c_dat2.text_input("Name")
                
                c1, c2, c3 = st.columns(3)
                ncost = c1.number_input("Cost (ทุน)", min_value=0.0)
                new_price = c2.number_input("Sell Price (ราคาขาย)", min_value=0.0)
                new_floor = c3.number_input("Floor Price (ต่ำสุด)", min_value=0.0)
                
                submitted = st.form_submit_button("Save Item to Stock", type="primary", use_container_width=True)
                
                if submitted:
                    if nid and nname and rotated_image_ready_to_save:
                        try:
                            # ขั้นตอนสำคัญ: จัดการรูปภาพก่อนบันทึก
                            # 1. ทำให้เป็นสี่เหลี่ยมจัตุรัสและย่อขนาด
                            final_img = make_square_and_resize(rotated_image_ready_to_save)
                            # 2. บันทึกลงเครื่อง
                            img_path = save_processed_image(final_img, nid)
                            
                            # 3. บันทึกข้อมูลลง Database
                            conn.execute('INSERT INTO products VALUES (?,?,?,?,?,?,"Available",0,NULL)', 
                                       (nid, nname, img_path, new_price, new_floor, ncost))
                            conn.commit()
                            st.success(f"Added {nname} successfully!")
                            
                            # เคลียร์รูปออกจาก memory หลังบันทึกเสร็จ
                            st.session_state.current_image = None
                            st.session_state.last_uploaded_file = None
                            st.rerun() # รีเฟรชเพื่อเคลียร์หน้าจอ
                            
                        except sqlite3.IntegrityError:
                            st.error(f"Error: ID '{nid}' นี้มีอยู่แล้ว")
                        except Exception as e:
                            st.error(f"An error occurred: {e}")
                    elif not rotated_image_ready_to_save:
                        st.error("กรุณาอัปโหลดรูปภาพก่อน")
                    else:
                        st.error("กรุณากรอก ID และชื่อสินค้า")

    with tab_hist:
        df_s = pd.read_sql("SELECT * FROM products WHERE status='Sold' ORDER BY sold_date DESC", conn)
        if not df_s.empty:
            df_s['profit'] = df_s['actual_sold_price'] - df_s['cost_price']
            st.dataframe(df_s[['product_id','name','actual_sold_price','profit']], use_container_width=True, hide_index=True)
        else:
            st.caption("No sales yet.")

conn.close()
