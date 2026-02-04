import streamlit as st
import pandas as pd
import base64
import os
from io import BytesIO
from datetime import datetime
from PIL import Image, ImageOps
from streamlit_option_menu import option_menu
from streamlit_gsheets import GSheetsConnection

# --- Setup หน้าเว็บ ---
st.set_page_config(page_title="HIGHCLASS", layout="wide", page_icon="✨")

# --- 🔐 SYSTEM: LOGIN ---
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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        logo_path = os.path.join(current_dir, "logo.png")
        try: st.image(logo_path, width=150)
        except: st.markdown("<h2 style='text-align: center;'>🔐 HIGHCLASS SHOP</h2>", unsafe_allow_html=True)
        
        with st.form("login_form"):
            user = st.text_input("Username", placeholder="User")
            pwd = st.text_input("Password", type="password", placeholder="Password")
            submitted = st.form_submit_button("LOGIN", use_container_width=True, type="primary")
            
            if submitted:
                try:
                    correct_user = st.secrets["credentials"]["username"]
                    correct_pass = st.secrets["credentials"]["password"]
                except:
                    st.error("⚠️ ไม่พบข้อมูล Login ใน Secrets")
                    st.stop()
                
                if user == correct_user and pwd == correct_pass:
                    st.session_state.logged_in = True
                    st.toast("Welcome back, Boss! 😎")
                    st.rerun()
                else:
                    st.error("❌ Access Denied!")

if not st.session_state.logged_in:
    check_login()
    st.stop()

# --- 👇 ส่วนจัดการ Google Sheets ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1a452nupXAJ_wLEJIE3NOd1bAJTqerphJfqUUhelq1ZY/edit?usp=sharing"
conn = st.connection("gsheets", type=GSheetsConnection)

# --- CSS & Theme ---
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

# --- Helper Functions ---
def get_data(worksheet_name):
    try:
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
        return df
    except Exception:
        return pd.DataFrame()

def save_data(df, worksheet_name):
    conn.update(spreadsheet=SHEET_URL, worksheet=worksheet_name, data=df)

def image_to_base64(pil_img):
    pil_img = pil_img.convert('RGB')
    pil_img.thumbnail((300, 300))
    buffered = BytesIO()
    pil_img.save(buffered, format="JPEG", quality=80)
    img_str = base64.b64encode(buffered.getvalue()).decode()
    return f"data:image/jpeg;base64,{img_str}"

# --- Sidebar ---
with st.sidebar:
    current_dir = os.path.dirname(os.path.abspath(__file__))
    logo_path = os.path.join(current_dir, "logo.png")
    try: st.image(logo_path, use_container_width=True)
    except: 
        st.markdown("## 🛍️ HIGHCLASS")
        st.caption("No logo found")

    # เพิ่มเมนู Shipping 🚚
    selected = option_menu(
        menu_title=None,
        options=["Dashboard", "Transactions", "Inventory", "Shipping", "Sold Items"],
        icons=["grid-1x2", "wallet", "box-seam-fill", "truck", "bag-check-fill"], 
        default_index=0,
    )
    st.divider()
    st.caption("Designed for Fiw")

# --- Load Data ---
df_trans = get_data("transactions")
df_prod = get_data("products")

if df_trans.empty:
    df_trans = pd.DataFrame(columns=['date', 'type', 'title', 'amount'])
if df_prod.empty:
    df_prod = pd.DataFrame(columns=['product_id', 'name', 'category', 'image_base64', 'sell_price', 'discount_price', 'cost_price', 'status', 'actual_sold_price', 'sold_date'])

# ✅ เพิ่มคอลัมน์สำหรับระบบขนส่ง (ถ้ายังไม่มี)
required_cols = ['shipping_status', 'customer_name', 'customer_address', 'tracking_no']
for col in required_cols:
    if col not in df_prod.columns:
        df_prod[col] = None

# === PAGE: DASHBOARD ===
if selected == "Dashboard":
    st.markdown("### 👋 HighClass Dashboard")
    
    if not df_trans.empty:
        inc = df_trans[df_trans['type']=='รายรับ']['amount'].sum()
        exp = df_trans[df_trans['type']=='รายจ่าย']['amount'].sum()
    else: inc, exp = 0, 0

    if not df_prod.empty:
        sold_items = df_prod[df_prod['status']=='Sold']
        total_revenue = sold_items['actual_sold_price'].sum()
        realized_profit = total_revenue - sold_items['cost_price'].sum()
        sold_count = len(sold_items)
        
        # นับจำนวนที่ต้องส่ง
        to_ship_count = len(sold_items[sold_items['shipping_status'] != 'Shipped'])

        available_items = df_prod[df_prod['status']=='Available']
        stock_val = available_items['cost_price'].sum()
        
        potential_revenue = available_items['sell_price'].sum()
        potential_profit = potential_revenue - stock_val
        total_investment = df_prod['cost_price'].sum()
    else: 
        total_revenue, stock_val, realized_profit, sold_count, to_ship_count = 0, 0, 0, 0, 0
        potential_revenue, potential_profit, total_investment = 0, 0, 0

    net_cash = (inc + total_revenue) - (exp + total_investment)

    st.markdown("##### ⚡ สถานะปัจจุบัน (Current Status)")
    col1, col2, col3, col4 = st.columns(4) # เพิ่มช่องแจ้งเตือนส่งของ
    col1.metric("✨ Net Profit", f"฿ {realized_profit:,.0f}", f"{sold_count} Sold")
    col2.metric("💵 Cash Balance", f"฿ {net_cash:,.0f}")
    col3.metric("📦 Stock Cost", f"฿ {stock_val:,.0f}")
    col4.metric("🚚 To Ship (ต้องส่ง)", f"{to_ship_count} ชิ้น", delta_color="inverse")
    
    st.divider()

    st.markdown("##### 🔮 อนาคตถ้าขายหมดเกลี้ยง (Future Projection)")
    c4, c5, c6 = st.columns(3)
    c4.metric("💰 Expected Revenue", f"฿ {potential_revenue:,.0f}")
    c5.metric("🚀 Potential Profit", f"฿ {potential_profit:,.0f}")
    c6.metric("🏗️ Total Investment", f"฿ {total_investment:,.0f}")

    st.divider()
    
    c_chart1, c_chart2 = st.columns(2)
    with c_chart1:
        st.subheader("📊 Stock by Category")
        if not df_prod.empty:
            stock_data = df_prod[df_prod['status']=='Available']['category'].value_counts()
            if not stock_data.empty: st.bar_chart(stock_data, color="#FF4B4B")
            else: st.info("No stock data.")
    with c_chart2:
        st.subheader("📈 Sales Trend")
        if not df_prod.empty:
            sales_data = df_prod[df_prod['status']=='Sold'].copy()
            if not sales_data.empty and 'sold_date' in sales_data.columns:
                sales_data['sold_date'] = pd.to_datetime(sales_data['sold_date'])
                daily_sales = sales_data.groupby(sales_data['sold_date'].dt.date)['actual_sold_price'].sum()
                st.line_chart(daily_sales, color="#00CC96")
            else: st.info("No sales yet.")

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
    
    with tab_sell:
        if 'category' not in df_prod.columns: df_prod['category'] = 'Uncategorized'
        all_cats = ["All"] + sorted(df_prod[df_prod['status']=='Available']['category'].astype(str).unique().tolist())
        
        c_search, c_filter = st.columns([2, 1])
        q = c_search.text_input("Search", placeholder="🔍 ID or Name...", label_visibility="collapsed")
        cat_filter = c_filter.selectbox("📂 Filter by Category", all_cats, label_visibility="collapsed")

        if not df_prod.empty:
            items = df_prod[df_prod['status'] == 'Available']
            if cat_filter != "All": items = items[items['category'] == cat_filter]
            if q:
                mask = items['product_id'].astype(str).str.contains(q, case=False) | items['name'].str.contains(q, case=False)
                items = items[mask]

            if items.empty: st.info(f"ไม่พบสินค้า")
            
            for i in range(0, len(items), 2):
                cols = st.columns(2)
                for idx, row in enumerate(items.iloc[i:i+2].itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            if pd.notna(row.image_base64) and str(row.image_base64).startswith('data:image'):
                                st.image(row.image_base64, use_container_width=True)
                            else: st.markdown("*(No Image)*")
                            
                            st.markdown(f"**{row.name}**")
                            st.caption(f"📂 {row.category} | ID: {row.product_id}")
                            
                            c1, c2 = st.columns(2)
                            c1.markdown(f"🏷️ Sell: **{row.sell_price:,.0f}**")
                            c2.markdown(f"📉 Floor: <span style='color:red'>{row.discount_price:,.0f}</span>", unsafe_allow_html=True)
                            st.markdown(f"🏭 Cost: `{row.cost_price:,.0f}`")
                            
                            unique_key_suffix = f"{row.product_id}_{row.Index}"
                            b_sell, b_cap, b_edit = st.columns([2, 1, 1])
                            
                            with b_sell:
                                with st.popover("⚡ Sell", use_container_width=True):
                                    st.markdown(f"Selling: **{row.name}**")
                                    actual_p = st.number_input("Price", value=float(row.sell_price), key=f"p_{unique_key_suffix}")
                                    
                                    if st.button("Confirm", key=f"b_sell_{unique_key_suffix}", type="primary"):
                                        # บันทึกขาย และตั้งสถานะส่งเป็น Pending
                                        df_prod.loc[row.Index, ['status','actual_sold_price','sold_date']] = ['Sold', actual_p, str(datetime.now())]
                                        df_prod.loc[row.Index, 'shipping_status'] = 'Pending' # รอส่ง
                                        save_data(df_prod, "products")
                                        st.toast(f"Sold! ไปที่เมนู Shipping เพื่อกรอกที่อยู่ 🚚")
                                        st.rerun()

                            with b_cap:
                                with st.popover("📋", use_container_width=True):
                                    st.markdown("##### 📝 Copy Caption")
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
        else: st.info("Stock is empty.")
    
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
                        'status': 'Available', 'actual_sold_price': 0, 'sold_date': None,
                        'shipping_status': None, 'customer_name': None, 'customer_address': None, 'tracking_no': None
                    }])
                    updated_stock = pd.concat([df_prod, new_item], ignore_index=True)
                    save_data(updated_stock, "products")
                    st.success(f"Added {nname}!")
                    st.rerun()
                else: st.error("Please fill all fields & upload image.")

    with tab_hist:
        if not df_prod.empty:
            sold_items = df_prod[df_prod['status']=='Sold']
            if not sold_items.empty:
                sold_items['profit'] = sold_items['actual_sold_price'] - sold_items['cost_price']
                st.dataframe(sold_items[['sold_date','name','category','actual_sold_price','profit']], use_container_width=True, hide_index=True)
            else: st.caption("No sales yet.")

# === 🚚 PAGE: SHIPPING (ระบบใหม่!) ===
elif selected == "Shipping":
    st.markdown("### 🚚 Delivery Center")
    
    # แยกแท็บ: ต้องส่ง vs ส่งแล้ว
    tab_to_ship, tab_shipped = st.tabs(["📦 To Ship (ต้องส่ง)", "✅ Shipped History (ส่งแล้ว)"])

    # --- TAB 1: รายการที่ต้องส่ง (ยังไม่ได้ส่ง) ---
    with tab_to_ship:
        # กรองสินค้าที่ขายแล้ว แต่สถานะยังไม่ใช่ Shipped
        pending_items = df_prod[(df_prod['status'] == 'Sold') & (df_prod['shipping_status'] != 'Shipped')]
        
        if pending_items.empty:
            st.success("🎉 เย้! ไม่มีของต้องส่ง (เคลียร์หมดแล้ว)")
        else:
            st.info(f"มีสินค้าต้องส่ง {len(pending_items)} รายการ")
            for idx, row in pending_items.iterrows():
                with st.expander(f"📦 {row['name']} (Sold: ฿{row['actual_sold_price']:,.0f})", expanded=True):
                    c_img, c_form = st.columns([1, 3])
                    
                    with c_img:
                        if pd.notna(row['image_base64']):
                            st.image(row['image_base64'], use_container_width=True)
                        else: st.write("No Image")
                    
                    with c_form:
                        # ฟอร์มกรอกที่อยู่
                        with st.form(key=f"ship_form_{row['product_id']}_{idx}"):
                            c1, c2 = st.columns(2)
                            cus_name = c1.text_input("ชื่อลูกค้า (Name)", value=row['customer_name'] if pd.notna(row['customer_name']) else "")
                            track_no = c2.text_input("เลขพัสดุ (Tracking No.)", value=row['tracking_no'] if pd.notna(row['tracking_no']) else "")
                            cus_addr = st.text_area("ที่อยู่จัดส่ง (Address)", value=row['customer_address'] if pd.notna(row['customer_address']) else "", height=100)
                            
                            btn_save = st.form_submit_button("💾 บันทึกข้อมูล & ยืนยันการส่ง (Mark as Shipped)", type="primary")
                            
                            if btn_save:
                                df_prod.at[idx, 'customer_name'] = cus_name
                                df_prod.at[idx, 'tracking_no'] = track_no
                                df_prod.at[idx, 'customer_address'] = cus_addr
                                df_prod.at[idx, 'shipping_status'] = 'Shipped' # เปลี่ยนสถานะเป็นส่งแล้ว
                                save_data(df_prod, "products")
                                st.toast(f"Shipping updated for {row['name']}!")
                                st.rerun()

    # --- TAB 2: ประวัติการส่ง (ส่งแล้ว) ---
    with tab_shipped:
        shipped_items = df_prod[df_prod['shipping_status'] == 'Shipped']
        if shipped_items.empty:
            st.info("ยังไม่มีรายการที่ส่งแล้ว")
        else:
            # โชว์แบบตารางสรุป
            st.dataframe(
                shipped_items[['sold_date', 'name', 'customer_name', 'tracking_no', 'customer_address']],
                use_container_width=True,
                hide_index=True
            )
            st.markdown("---")
            # โชว์การ์ดเผื่อดูรูป
            for idx, row in shipped_items.iterrows():
                with st.expander(f"✅ {row['name']} - {row['customer_name']}"):
                    st.write(f"**Tracking:** {row['tracking_no']}")
                    st.write(f"**Address:** {row['customer_address']}")

# === PAGE: SOLD ITEMS ===
elif selected == "Sold Items":
    st.markdown("### ✅ Sold Out Gallery")
    if not df_prod.empty:
        sold_items = df_prod[df_prod['status'] == 'Sold']
        if 'sold_date' in sold_items.columns:
            sold_items = sold_items.sort_values(by='sold_date', ascending=False)

        if sold_items.empty:
            st.info("ยังไม่มีสินค้าที่ขายออกไป สู้ๆ ครับ! ✌️")
        else:
            total_rev = sold_items['actual_sold_price'].sum()
            total_profit = total_rev - sold_items['cost_price'].sum()
            st.metric("🎉 Total Sales Volume", f"฿ {total_rev:,.0f}", f"Profit: ฿ {total_profit:,.0f}")
            st.divider()

            for i in range(0, len(sold_items), 2):
                cols = st.columns(2)
                for idx, row in enumerate(sold_items.iloc[i:i+2].itertuples()):
                    with cols[idx]:
                        with st.container(border=True):
                            if pd.notna(row.image_base64) and str(row.image_base64).startswith('data:image'):
                                st.image(row.image_base64, use_container_width=True)
                            else: st.markdown("*(No Image)*")
                            
                            st.markdown(f"**{row.name}**")
                            # แสดงสถานะส่งของตรงนี้ด้วย
                            ship_stat = row.shipping_status if pd.notna(row.shipping_status) else "Pending"
                            color = "green" if ship_stat == "Shipped" else "orange"
                            st.markdown(f"🚚 Status: <span style='color:{color}'>**{ship_stat}**</span>", unsafe_allow_html=True)
                            
                            c1, c2 = st.columns(2)
                            c1.markdown(f"💰 Sold: **{row.actual_sold_price:,.0f}**")
                            profit = row.actual_sold_price - row.cost_price
                            if profit > 0: c2.markdown(f"🔥 <span style='color:green'>+{profit:,.0f}</span>", unsafe_allow_html=True)
                            else: c2.markdown(f"🔻 <span style='color:red'>{profit:,.0f}</span>", unsafe_allow_html=True)
                            
                            unique_key_sold = f"restore_{row.product_id}_{row.Index}"
                            with st.popover("❌ Cancel / Restock", use_container_width=True):
                                st.markdown(f"ดึง **{row.name}** กลับไปขายใหม่?")
                                if st.button("ยืนยัน", key=unique_key_sold, type="primary"):
                                    df_prod.at[row.Index, 'status'] = 'Available'
                                    df_prod.at[row.Index, 'actual_sold_price'] = 0
                                    df_prod.at[row.Index, 'sold_date'] = None
                                    df_prod.at[row.Index, 'shipping_status'] = None
                                    save_data(df_prod, "products")
                                    st.toast(f"Restored {row.name}!")
                                    st.rerun()
    else: st.info("No data available.")
