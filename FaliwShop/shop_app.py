import streamlit as st
import pandas as pd
import base64
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="Faliw Manager", layout="wide")

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
        st.markdown("<h2 style='text-align: center;'>🔐 FALIW SHOP ADMIN</h2>", unsafe_allow_html=True)
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
    st.markdown("##  FALIW MANAGER")
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Transactions", "Inventory"],
        icons=["grid-1x2", "wallet", "box-seam-fill"], 
        default_index=2, # เริ่มต้นที่หน้า Inventory จะได้ลองเพิ่มของก่อน
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
    tab_sell, tab_add, tab_hist = st.tabs(["🛍️ Shop", "➕ Add Item", "📊 Sales Log"])
    
    # --- TAB: SHOP ---
    with tab_sell:
        q = st.text_input("Search", placeholder="🔍 ID or Name...", label_visibility="collapsed")
        
        if not df_prod.empty:
            items = df_prod[df_prod['status'] == 'Available']
            if q:
                mask = items['product_id'].astype(str).str.contains(q, case=False) | items['name'].str.contains(q, case=False)
                items = items[mask]

            if items.empty: st.caption("No items.")
            
            # Loop แสดงสินค้า
            for i in range(0, len(items), 2):
                cols = st.columns(2)
                for idx, row in enumerate(items.iloc[i:i+2].itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            # แสดงรูปจาก Base64 code
                            if pd.notna(row.image_base64) and str(row.image_base64).startswith('data:image'):
                                st.image(row.image_base64, use_container_width=True)
                            else:
                                st.markdown("*(No Image)*")
                            
                            st.markdown(f"**{row.name}**")
                            
                            # --- ส่วนที่เพิ่ม: แสดง Cost และ Floor ---
                            c1, c2 = st.columns(2)
                            c1.markdown(f"🏷️ Sell: **{row.sell_price:,.0f}**")
                            c2.markdown(f"📉 Floor: <span style='color:red'>{row.discount_price:,.0f}</span>", unsafe_allow_html=True)
                            
                            c3, c4 = st.columns(2)
                            c3.markdown(f"🏭 Cost: `{row.cost_price:,.0f}`")
                            c4.caption(f"ID: {row.product_id}")
                            # -------------------------------------

                            # สร้าง Key ไม่ให้ซ้ำ
                            unique_key_suffix = f"{row.product_id}_{row.Index}"
                            
                            with st.popover("⚡ Sell", use_container_width=True):
                                st.markdown(f"Selling: **{row.name}**")
                                st.info(f"Capital (Cost): {row.cost_price:,.0f} | Floor Price: {row.discount_price:,.0f}")
                                
                                actual_p = st.number_input("Sold Price", value=float(row.sell_price), key=f"p_{unique_key_suffix}")
                                
                                # เตือนถ้าขายต่ำกว่าทุนหรือ Floor
                                if actual_p < row.cost_price:
                                    st.warning("⚠️ ขาดทุนนะ (Below Cost)!")
                                elif actual_p < row.discount_price:
                                    st.warning("⚠️ ต่ำกว่าราคา Floor!")

                                if st.button("Confirm Sale", key=f"b_{unique_key_suffix}", type="primary"):
                                    df_prod.loc[row.Index, ['status','actual_sold_price','sold_date']] = ['Sold', actual_p, str(datetime.now())]
                                    save_data(df_prod, "products")
                                    st.toast(f"Sold {row.name}!")
                                    st.rerun()
        else:
            st.info("Stock is empty. Go to 'Add Item' tab.")
    
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
            c3, c4, c5 = st.columns(3)
            ncost = c3.number_input("Cost", min_value=0.0)
            nprice = c4.number_input("Sell Price", min_value=0.0)
            nfloor = c5.number_input("Floor Price", min_value=0.0)
            
            if st.form_submit_button("Save Item", type="primary"):
                if nid and nname and uploaded_file:
                    img_str = image_to_base64(image)
                    new_item = pd.DataFrame([{
                        'product_id': nid, 'name': nname, 'image_base64': img_str,
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
                st.dataframe(sold_items[['sold_date','name','actual_sold_price','profit']], use_container_width=True, hide_index=True)
            else:
                st.caption("No sales yet.")
