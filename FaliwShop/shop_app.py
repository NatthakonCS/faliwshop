import streamlit as st
import pandas as pd
import os
from datetime import datetime
from PIL import Image, ImageOps
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="Shop Manager", layout="wide")

# URL Google Sheets ของฟิว
SHEET_URL = "https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing"

# เชื่อมต่อ Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS Customization ---
st.markdown("""
<style>
    .block-container { padding-top: 1.5rem; padding-bottom: 3rem; }
    footer {visibility: hidden;}
    .stButton>button {
        border-radius: 12px; font-weight: 600; border: none;
        box-shadow: 0 2px 4px rgba(0,0,0,0.2); transition: all 0.2s;
    }
    .stButton>button:hover { transform: translateY(-2px); box-shadow: 0 4px 8px rgba(0,0,0,0.3); }
    div[data-testid="stVerticalBlock"] > div[style*="background-color"] {
        border-radius: 16px; border: 1px solid rgba(255,255,255,0.1);
        box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    .stTextInput>div>div>input { border-radius: 10px; }
    header[data-testid="stHeader"] { background-color: transparent; }
</style>
""", unsafe_allow_html=True)

IMAGE_FOLDER = 'product_images'
if not os.path.exists(IMAGE_FOLDER):
    os.makedirs(IMAGE_FOLDER)

# --- Helper Functions (ระบบหลังบ้านใหม่) ---

def get_data(worksheet_name):
    """อ่านข้อมูลจาก Google Sheets"""
    try:
        # ttl=0 คือห้ามจำค่าเก่า ให้ดึงใหม่ทุกครั้ง
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
        return df
    except Exception:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    """บันทึกข้อมูลทับลง Google Sheets"""
    conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=df)

def make_square_and_resize(pil_img, target_size=800):
    pil_img = pil_img.convert('RGB')
    width, height = pil_img.size
    max_side = max(width, height)
    new_img = Image.new('RGB', (max_side, max_side), (255, 255, 255))
    offset = ((max_side - width) // 2, (max_side - height) // 2)
    new_img.paste(pil_img, offset)
    if max_side > target_size:
        new_img = new_img.resize((target_size, target_size), Image.LANCZOS)
    return new_img

def save_processed_image(pil_img, product_id):
    filename = f"{product_id}.jpg"
    filepath = os.path.join(IMAGE_FOLDER, filename)
    pil_img.save(filepath, 'JPEG', quality=90)
    return filepath

# --- Sidebar Menu ---
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
        default_index=0,
        styles={
            "container": {"padding": "0!important", "background-color": "transparent"},
            "icon": {"color": "#888", "font-size": "18px"}, 
            "nav-link": {"font-size": "16px", "text-align": "left", "margin":"5px", "border-radius": "10px"},
            "nav-link-selected": {"background-color": "#FF512F", "color": "white", "font-weight": "600"},
        }
    )

# --- โหลดข้อมูลเตรียมไว้ ---
df_trans = get_data("transactions")
df_prod = get_data("products")

# ถ้าตารางยังว่าง (เพิ่งสร้างใหม่) ให้สร้าง Column รอไว้
if df_trans.empty:
    df_trans = pd.DataFrame(columns=['date', 'type', 'title', 'amount'])
if df_prod.empty:
    df_prod = pd.DataFrame(columns=['product_id', 'name', 'image_path', 'sell_price', 'discount_price', 'cost_price', 'status', 'actual_sold_price', 'sold_date'])

# === PAGE: DASHBOARD ===
if selected == "Dashboard":
    st.markdown("### 👋 Overview")
    
    # คำนวณยอด
    if not df_trans.empty:
        inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum()
        exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum()
    else:
        inc, exp = 0, 0

    if not df_prod.empty:
        sold = df_prod[df_prod['status']=='Sold']
        rev_clothes = sold['actual_sold_price'].sum()
        cost_clothes = sold['cost_price'].sum()
        profit_clothes = rev_clothes - cost_clothes
        stock_val = df_prod[df_prod['status']=='Available']['cost_price'].sum()
        sold_count = len(sold)
    else:
        rev_clothes, cost_clothes, profit_clothes, stock_val, sold_count = 0, 0, 0, 0, 0

    net = (inc + rev_clothes) - (exp + cost_clothes)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        with st.container(border=True):
            st.metric("✨ Net Profit (Clothes)", f"฿ {profit_clothes:,.0f}", f"{sold_count} items sold")
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
                # สร้างข้อมูลใหม่บรรทัดเดียว
                new_row = pd.DataFrame([{
                    'date': str(d_date), 
                    'type': d_type, 
                    'title': d_title, 
                    'amount': d_amt
                }])
                # รวมกับของเดิม
                updated_df = pd.concat([df_trans, new_row], ignore_index=True)
                # บันทึกลง Google Sheets
                save_data(updated_df, "transactions")
                st.toast("Saved successfully!")
                st.rerun()

    st.markdown("#### 📜 History")
    if not df_trans.empty:
        st.dataframe(df_trans.sort_index(ascending=False), use_container_width=True, hide_index=True)

# === PAGE: INVENTORY ===
elif selected == "Inventory":
    st.markdown("### 👕 Stock Management")
    tab_sell, tab_add, tab_hist = st.tabs(["🛍️ Shop", "➕ Add Item", "📊 Sales Log"])
    
    # --- TAB: SHOP ---
    with tab_sell:
        col_search, _ = st.columns([3, 1])
        q = col_search.text_input("Search", placeholder="🔍 Find by ID or Name...", label_visibility="collapsed")
        
        # Filter เฉพาะสินค้าที่ยังไม่ขาย (Available)
        if not df_prod.empty:
            available_items = df_prod[df_prod['status'] == 'Available']
            
            if q:
                # ค้นหาใน ID หรือ ชื่อ
                mask = available_items['product_id'].astype(str).str.contains(q, case=False, na=False) | \
                       available_items['name'].str.contains(q, case=False, na=False)
                display_df = available_items[mask]
            else:
                display_df = available_items

            if display_df.empty:
                st.caption("No items found.")
            else:
                # Loop แสดงสินค้า
                for i in range(0, len(display_df), 2):
                    cols = st.columns(2)
                    batch = display_df.iloc[i:i+2]
                    for idx, row in enumerate(batch.itertuples()):
                        with cols[idx]:
                            with st.container(border=True):
                                # แสดงรูป
                                if pd.notna(row.image_path) and os.path.exists(str(row.image_path)):
                                    st.image(str(row.image_path), use_container_width=True)
                                else:
                                    st.markdown("*(No Image)*")
                                
                                st.markdown(f"**{row.name}**")
                                st.caption(f"ID: {row.product_id}")
                                c1, c2 = st.columns(2)
                                c1.markdown(f"🏷️ **{row.sell_price:,.0f}**")
                                c2.markdown(f"🔒 Floor: {row.discount_price:,.0f}")
                                
                                b_sell, b_del = st.columns([4, 1])
                                
                                # ปุ่มขาย
                                with b_sell:
                                    with st.popover("⚡ Sell", use_container_width=True):
                                        st.markdown(f"Selling: **{row.name}**")
                                        actual_p = st.number_input("Sold Price", value=float(row.sell_price), key=f"p_{row.product_id}")
                                        if st.button("Confirm Sale", key=f"b_{row.product_id}", type="primary"):
                                            # อัปเดตสถานะใน DataFrame
                                            df_prod.loc[df_prod['product_id'] == row.product_id, 'status'] = 'Sold'
                                            df_prod.loc[df_prod['product_id'] == row.product_id, 'actual_sold_price'] = actual_p
                                            df_prod.loc[df_prod['product_id'] == row.product_id, 'sold_date'] = str(datetime.now())
                                            
                                            save_data(df_prod, "products")
                                            st.rerun()

                                # ปุ่มลบ
                                with b_del:
                                    with st.popover("🗑️", use_container_width=True):
                                        st.markdown(f"Delete {row.name}?")
                                        if st.button("Yes", key=f"del_{row.product_id}", type="primary"):
                                            # ลบแถวออกจาก DataFrame
                                            df_prod = df_prod[df_prod['product_id'] != row.product_id]
                                            save_data(df_prod, "products")
                                            st.toast(f"Deleted {row.name}")
                                            st.rerun()
        else:
            st.info("Stock is empty. Go to 'Add Item' tab.")

    # --- TAB: ADD ITEM ---
    with tab_add:
        with st.container(border=True):
            st.markdown("#### 1️⃣ Upload & Rotate Image")
            uploaded_file = st.file_uploader("Choose Image", type=['png','jpg','jpeg'], label_visibility="collapsed")
            
            if 'current_image' not in st.session_state: st.session_state.current_image = None
            if 'last_uploaded_file' not in st.session_state: st.session_state.last_uploaded_file = None

            if uploaded_file is not None and uploaded_file != st.session_state.last_uploaded_file:
                try:
                    image = Image.open(uploaded_file)
                    image = ImageOps.exif_transpose(image) 
                    st.session_state.current_image = image
                    st.session_state.last_uploaded_file = uploaded_file
                except:
                    st.error("File Error")

            rotated_image_ready_to_save = None
            if st.session_state.current_image is not None:
                col_prev, col_rot = st.columns([2, 1], gap="medium")
                with col_prev:
                    st.image(st.session_state.current_image, caption="Preview", use_container_width=True)
                with col_rot:
                    if st.button("🔄 Left (90°)", use_container_width=True):
                        st.session_state.current_image = st.session_state.current_image.rotate(90, expand=True)
                        st.rerun()
                    if st.button("🔃 Right (90°)", use_container_width=True):
                        st.session_state.current_image = st.session_state.current_image.rotate(-90, expand=True)
                        st.rerun()
                rotated_image_ready_to_save = st.session_state.current_image
                st.divider()

            st.markdown("#### 2️⃣ Product Details")
            with st.form("add_prod_form", clear_on_submit=True):
                c_dat1, c_dat2 = st.columns(2)
                nid = c_dat1.text_input("ID (Unique)")
                nname = c_dat2.text_input("Name")
                c1, c2, c3 = st.columns(3)
                ncost = c1.number_input("Cost", min_value=0.0)
                new_price = c2.number_input("Sell Price", min_value=0.0)
                new_floor = c3.number_input("Floor Price", min_value=0.0)
                
                submitted = st.form_submit_button("Save Item", type="primary", use_container_width=True)
                
                if submitted:
                    # เช็คว่า ID ซ้ำไหม
                    is_duplicate = False
                    if not df_prod.empty:
                        if nid in df_prod['product_id'].astype(str).values:
                            is_duplicate = True

                    if nid and nname and rotated_image_ready_to_save and not is_duplicate:
                        # Save Image
                        final_img = make_square_and_resize(rotated_image_ready_to_save)
                        img_path = save_processed_image(final_img, nid)
                        
                        # Add Data to DataFrame
                        new_item = pd.DataFrame([{
                            'product_id': nid,
                            'name': nname,
                            'image_path': img_path,
                            'sell_price': new_price,
                            'discount_price': new_floor,
                            'cost_price': ncost,
                            'status': 'Available',
                            'actual_sold_price': 0,
                            'sold_date': None
                        }])
                        
                        updated_stock = pd.concat([df_prod, new_item], ignore_index=True)
                        save_data(updated_stock, "products")
                        
                        st.success(f"Added {nname}!")
                        st.session_state.current_image = None
                        st.session_state.last_uploaded_file = None
                        st.rerun()
                    elif is_duplicate:
                        st.error(f"Error: ID {nid} already exists!")
                    else:
                        st.error("Please upload image and fill ID/Name.")

    # --- TAB: SALES LOG ---
    with tab_hist:
        if not df_prod.empty:
            df_s = df_prod[df_prod['status']=='Sold'].copy()
            if not df_s.empty:
                df_s['profit'] = df_s['actual_sold_price'] - df_s['cost_price']
                st.dataframe(df_s[['product_id','name','actual_sold_price','profit','sold_date']], use_container_width=True, hide_index=True)
            else:
                st.caption("No sales yet.")
        else:
            st.caption("No data.")
