import streamlit as st
import pandas as pd
import geopandas as gpd
from shapely.geometry import LineString, Point, MultiLineString
import json
from datetime import datetime

st.set_page_config(page_title="ArcGIS Arabic Fix", layout="wide")
st.title("🌍 ArcGIS to CSV (Arabic Language Fix)")

st.sidebar.header("🛠️ Settings")
swap_xy = st.sidebar.checkbox("Swap X and Y (Fix Position)", value=True)

uploaded_file = st.file_uploader("Upload ArcGIS JSON", type=['json'])

if uploaded_file is not None:
    try:
        data = json.load(uploaded_file)
        sr = data.get('spatialReference', {})
        wkid = sr.get('latestWkid') or sr.get('wkid') or 4326
        
        if 'features' in data:
            features_list = []
            for feat in data['features']:
                attribs = feat.get('attributes', {}).copy()
                geom_input = feat.get('geometry', {})
                if not geom_input: continue

                def fix_coords(coords_list):
                    return [(pt[1], pt[0]) if swap_xy else (pt[0], pt[1]) for pt in coords_list]

                geometry = None
                if 'paths' in geom_input:
                    paths = [fix_coords(p) for p in geom_input['paths']]
                    geometry = MultiLineString(paths) if len(paths) > 1 else LineString(paths[0])
                elif 'rings' in geom_input: # دعم المضلعات
                    from shapely.geometry import Polygon
                    geometry = Polygon(geom_input['rings'][0])
                elif 'x' in geom_input and 'y' in geom_input:
                    x, y = (geom_input['y'], geom_input['x']) if swap_xy else (geom_input['x'], geom_input['y'])
                    geometry = Point(x, y)

                if geometry:
                    attribs['geometry'] = geometry
                    features_list.append(attribs)

            if features_list:
                df = pd.DataFrame(features_list)

                # --- 1. معالجة التاريخ وتثبيته كنص YYYY-MM-DD ---
                def format_date_final(val):
                    if isinstance(val, (int, float)) and val > 100000000000:
                        try:
                            return datetime.fromtimestamp(val / 1000.0).strftime('%Y-%m-%d')
                        except:
                            return str(val)
                    return str(val) if val is not None else ""

                # تطبيق تحويل التاريخ على كل الأعمدة عدا الجيومتري
                for col in df.columns:
                    if col != 'geometry':
                        df[col] = df[col].apply(format_date_final)

                # --- 2. التحويل الجغرافي والترميز ---
                # إنشاء GeoDataFrame من الـ DataFrame
                gdf = gpd.GeoDataFrame(df, crs=f"EPSG:{wkid}")
                
                # تحويل للنظام العالمي WGS84
                gdf_wgs84 = gdf.to_crs(epsg=4326)

                st.success(f"✅ Processed {len(gdf_wgs84)} features. Arabic text fixed.")

                # --- 3. تجهيز الـ CSV النهائي ---
                csv_df = gdf_wgs84.copy()
                
                # إضافة خط الطول والعرض (لأول نقطة في المسار أو لموقع النقطة)
                csv_df['Lat_Long_Combined'] = csv_df['geometry'].apply(lambda g: f"{g.centroid.y}, {g.centroid.x}" if g else "")
                csv_df['WKT_Geometry'] = csv_df['geometry'].apply(lambda g: g.wkt if g else "")

                # تنظيف البيانات المعقدة (Lists/Dicts) لضمان عدم نقص الصفوف
                for c in csv_df.columns:
                    if c != 'geometry' and csv_df[c].apply(lambda x: isinstance(x, (list, dict))).any():
                        csv_df[c] = csv_df[c].astype(str)

                # أزرار التحميل
                col1, col2 = st.columns(2)
                
                with col1:
                    # تصدير GeoJSON (التواريخ ستكون نصوص بالصيغة المطلوبة)
                    st.download_button("📥 Download GeoJSON", gdf_wgs84.to_json(), "formatted_data.geojson")
                
                with col2:
                    # تصدير CSV مع التأكد من ترميز اللغة العربية UTF-8-SIG
                    # هامة جداً لظهور اللغة العربية في إكسل
                    csv_output = csv_df.drop(columns='geometry').to_csv(index=False, encoding='utf-8-sig')
                    st.download_button("📥 Download CSV (Arabic Fixed)", csv_output, "formatted_data.csv")

                st.subheader("Preview (Arabic Text & Formatted Dates)")
                st.dataframe(csv_df.drop(columns='geometry').head(10))
            else:
                st.error("No valid geometry found in features.")
    except Exception as e:
        st.error(f"Error during processing: {str(e)}")