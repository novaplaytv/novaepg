import requests
import os
import gzip
import json
import re
import time
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
API_FETCH_URL = "https://www.open-epg.com/app/epgfetch.php"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
TVMAX_FILE = os.path.join(BASE_DIR, "novaepg/tvmax/tvmax.xml")

os.makedirs(TEMP_DIR, exist_ok=True)

def parse_time(t_str):
    if not t_str: return None
    # Formato: 20260905112000 +0000
    try:
        clean_t = t_str.split()[0][:14]
        return datetime.strptime(clean_t, "%Y%m%d%H%M%S")
    except:
        return None

def format_epg_time(dt):
    return dt.strftime("%Y%m%d%H%M%S")

def get_files_list():
    print("📡 Obteniendo lista de archivos de Open-EPG...")
    try:
        r = requests.get(API_FETCH_URL, timeout=30)
        r.raise_for_status()
        return r.json()
    except Exception as e:
        print(f"❌ Error al obtener la lista: {e}")
        return []

def download_file(url, country):
    filename = os.path.basename(url)
    local_path = os.path.join(TEMP_DIR, filename)
    print(f"📥 Descargando {country} ({filename})...")
    try:
        # Algunos servidores de Open-EPG son caprichosos, usamos reintentos
        for _ in range(3):
            try:
                r = requests.get(url, timeout=60, stream=True)
                r.raise_for_status()
                with open(local_path, 'wb') as f:
                    for chunk in r.iter_content(chunk_size=8192):
                        f.write(chunk)
                return local_path
            except:
                time.sleep(2)
    except Exception as e:
        print(f"   ⚠️ Fallo al descargar {country}: {e}")
    return None

def extract_channels_and_programs(xml_path, is_gz=False):
    channels = []
    programs = []

    # Regex simples para velocidad (XMLTV es predecible)
    c_regex = re.compile(r'<channel id="(.*?)">.*?<display-name.*?>(.*?)</display-name>(.*?)</channel>', re.DOTALL)
    p_regex = re.compile(r'<programme start="(.*?)" stop="(.*?)" channel="(.*?)">.*?<title.*?>(.*?)</title>(.*?)</programme>', re.DOTALL)
    icon_regex = re.compile(r'<icon src="(.*?)"')
    desc_regex = re.compile(r'<desc.*?>(.*?)</desc>')

    try:
        opener = gzip.open(xml_path, 'rt', encoding='utf-8', errors='ignore') if is_gz else open(xml_path, 'r', encoding='utf-8', errors='ignore')
        with opener as f:
            content = f.read()

            # Extraer canales
            for match in c_regex.finditer(content):
                cid, name, extra = match.groups()
                icon = icon_regex.search(extra)
                channels.append({
                    "id": cid,
                    "name": name,
                    "logo": icon.group(1) if icon else ""
                })

            # Extraer programas (solo futuros o actuales)
            now = datetime.now()
            for match in p_regex.finditer(content):
                start_str, stop_str, cid, title, extra = match.groups()
                start_dt = parse_time(start_str)
                stop_dt = parse_time(stop_str)

                if stop_dt and stop_dt > now:
                    desc = desc_regex.search(extra)
                    programs.append({
                        "cid": cid,
                        "t": title,
                        "s": start_str.split()[0][:14],
                        "e": stop_str.split()[0][:14],
                        "d": desc.group(1) if desc else ""
                    })
    except Exception as e:
        print(f"   ❌ Error procesando {xml_path}: {e}")

    return channels, programs

def run():
    files = get_files_list()
    if not files: return

    all_channels = []
    all_programs = []
    countries_data = []

    # 1. Procesar TVMAX primero (Excepción)
    if os.path.exists(TVMAX_FILE):
        print("💎 Procesando TVMAX (Excepción)...")
        c, p = extract_channels_and_programs(TVMAX_FILE)
        all_channels.extend(c)
        all_programs.extend(p)

    # 2. Procesar Open-EPG
    # Limitamos para no saturar en pruebas, pero el script final debe bajar todos
    for item in files:
        country_name = item.get('cou', 'Desconocido')
        url = item.get('url')
        if not url: continue

        # Bajar archivo
        path = download_file(url, country_name)
        if path:
            c, p = extract_channels_and_programs(path)
            all_channels.extend(c)
            all_programs.extend(p)
            countries_data.append({
                "name": country_name,
                "count": len(c),
                "updated": item.get('age', 'Hoy')
            })
            # Borrar temporal para no llenar disco
            try: os.remove(path)
            except: pass

    # 3. Generar JSON optimizado para WEB
    print("🚀 Generando archivos para WEB y APP...")

    # Agrupar programas por canal
    db = {}
    for c in all_channels:
        db[c['id']] = {
            "n": c['name'],
            "l": c['logo'],
            "p": []
        }

    for p in all_programs:
        if p['cid'] in db:
            # Solo guardamos los próximos 5 programas para ligereza
            if len(db[p['cid']]['p']) < 8:
                db[p['cid']]['p'].append({
                    "t": p['t'],
                    "s": p['s'],
                    "e": p['e'],
                    "d": p['d']
                })

    # Convertir a lista y ordenar
    final_list = []
    for cid, data in db.items():
        if data['p']:
            data['p'].sort(key=lambda x: x['s'])
            final_list.append({
                "id": cid,
                "n": data['n'],
                "l": data['l'],
                "p": data['p']
            })

    final_list.sort(key=lambda x: x['n'].lower())

    # Guardar archivos
    with open(os.path.join(DATA_DIR, "epg.json"), "w", encoding="utf-8") as f:
        json.dump(final_list, f, separators=(',', ':'), ensure_ascii=False)

    with open(os.path.join(DATA_DIR, "countries.json"), "w", encoding="utf-8") as f:
        json.dump(countries_data, f, indent=2, ensure_ascii=False)

    # 4. GENERAR XMLTV PARA LA APP (guide.xml y guide.xml.gz)
    print("📺 Generando guide.xml para la APP...")
    XML_OUTPUT = os.path.join(BASE_DIR, "guide.xml")
    GZ_OUTPUT = os.path.join(BASE_DIR, "guide.xml.gz")

    with open(XML_OUTPUT, 'w', encoding='utf-8') as x:
        x.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        x.write('<tv generator-info-name="NovaEPG">\n')

        # Escribir canales
        for c in all_channels:
            x.write(f'  <channel id="{c["id"]}">\n')
            x.write(f'    <display-name>{c["name"]}</display-name>\n')
            if c["logo"]: x.write(f'    <icon src="{c["logo"]}" />\n')
            x.write('  </channel>\n')

        # Escribir programas
        for p in all_programs:
            # Sanitizar textos para XML
            def clean(t):
                return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')

            x.write(f'  <programme start="{p["s"]} +0000" stop="{p["e"]} +0000" channel="{p["cid"]}">\n')
            x.write(f'    <title lang="es">{clean(p["t"])}</title>\n')
            if p["d"]: x.write(f'    <desc lang="es">{clean(p["d"])}</desc>\n')
            x.write('  </programme>\n')

        x.write('</tv>')

    print("📦 Comprimiendo a guide.xml.gz...")
    with open(XML_OUTPUT, 'rb') as f_in:
        with gzip.open(GZ_OUTPUT, 'wb') as f_out:
            f_out.writelines(f_in)

    print(f"✅ Proceso terminado. XML y GZ generados en la raíz.")

if __name__ == "__main__":
    run()
