import requests
import os
import gzip
import json
import re
import time
from datetime import datetime, timedelta, timezone

# --- CONFIGURACIÓN ---
API_FETCH_URL = "https://www.open-epg.com/app/epgfetch.php"
PLUTO_TV_URL = "https://i.mjh.nz/PlutoTV/all.xml.gz"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
EPG_DIR = os.path.join(BASE_DIR, "epg")
TEMP_DIR = os.path.join(DATA_DIR, "temp")
TVMAX_FILE = os.path.join(BASE_DIR, "novaepg/tvmax/tvmax.xml")
NOVASPORTS_FILE = os.path.join(BASE_DIR, "novaepg/novasports/novasports.xml")

def parse_time(t_str):
    if not t_str: return None
    try:
        partes = t_str.split()
        fecha_base = partes[0][:14]
        dt = datetime.strptime(fecha_base, "%Y%m%d%H%M%S")
        if len(partes) > 1:
            off = partes[1]
            signo = 1 if off[0] == '+' else -1
            try:
                horas = int(off[1:3])
                mins = int(off[3:5])
                dt = dt - timedelta(minutes=signo * (horas * 60 + mins))
            except: pass
        return dt
    except:
        return None

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
    c_regex = re.compile(r'<channel id="(.*?)">.*?<display-name.*?>(.*?)</display-name>(.*?)</channel>', re.DOTALL)
    p_regex = re.compile(r'<programme start="(.*?)" stop="(.*?)" channel="(.*?)">.*?<title.*?>(.*?)</title>(.*?)</programme>', re.DOTALL)
    icon_regex = re.compile(r'<icon src="(.*?)"')
    desc_regex = re.compile(r'<desc.*?>(.*?)</desc>')

    try:
        opener = gzip.open(xml_path, 'rt', encoding='utf-8', errors='ignore') if xml_path.endswith('.gz') or is_gz else open(xml_path, 'r', encoding='utf-8', errors='ignore')
        with opener as f:
            content = f.read()
            for match in c_regex.finditer(content):
                cid, name, extra = match.groups()
                icon = icon_regex.search(extra)
                channels.append({"id": cid, "name": name, "logo": icon.group(1) if icon else ""})

            now = datetime.now(timezone.utc).replace(tzinfo=None)
            for match in p_regex.finditer(content):
                start_str, stop_str, cid, title, extra = match.groups()
                start_dt = parse_time(start_str)
                stop_dt = parse_time(stop_str)
                if stop_dt and stop_dt > now:
                    desc = desc_regex.search(extra)
                    programs.append({"cid": cid, "t": title, "s": start_dt.strftime("%Y%m%d%H%M%S"), "e": stop_dt.strftime("%Y%m%d%H%M%S"), "d": desc.group(1) if desc else ""})
    except Exception as e:
        print(f"   ❌ Error procesando {xml_path}: {e}")
    return channels, programs

def run():
    files = get_files_list()
    if not files: return

    os.makedirs(TEMP_DIR, exist_ok=True)
    os.makedirs(EPG_DIR, exist_ok=True)
    os.makedirs(DATA_DIR, exist_ok=True)

    sources = []

    # 1. Fuentes Locales
    if os.path.exists(TVMAX_FILE):
        print("💎 Procesando TVMAX...")
        c, p = extract_channels_and_programs(TVMAX_FILE)
        sources.append({"name": "TVMAX", "channels": c, "programs": p, "age": "Ahora", "is_external": False})

    if os.path.exists(NOVASPORTS_FILE):
        print("⚽ Procesando NOVASPORTS...")
        c, p = extract_channels_and_programs(NOVASPORTS_FILE)
        sources.append({"name": "NOVASPORTS", "channels": c, "programs": p, "age": "24/7", "is_external": False})

    # 2. Pluto TV (Externo) - Forzamos descarga para asegurar rastro en log
    print("🎬 INICIANDO PROCESAMIENTO PLUTO TV...")
    path_pluto = download_file(PLUTO_TV_URL, "Pluto TV")
    if path_pluto:
        c, p = extract_channels_and_programs(path_pluto)
        print(f"   ✅ Pluto TV procesado: {len(c)} canales y {len(p)} programas futuros.")
        sources.append({"name": "Pluto TV", "channels": c, "programs": p, "age": "Ahora", "is_external": True})
        try: os.remove(path_pluto)
        except: pass
    else:
        print("   ❌ Error crítico: No se pudo descargar el EPG de Pluto TV.")

    # 3. Open-EPG
    for item in files:
        country_name = item.get('cou', 'Desconocido')
        url = item.get('url')
        if not url: continue
        path = download_file(url, country_name)
        if path:
            c, p = extract_channels_and_programs(path)
            sources.append({"name": country_name, "channels": c, "programs": p, "age": item.get('age', 'Hoy'), "is_external": False})
            try: os.remove(path)
            except: pass

    # 4. Generar archivos finales
    print("🚀 Compilando base de datos de búsqueda y JSONs...")
    final_countries = []
    search_db = []

    for src in sources:
        country_slug = re.sub(r'[^a-zA-Z0-9]', '_', src['name']).lower()
        filename = f"epg_{country_slug}.json"
        country_db = []
        chan_map = {c['id']: {"id": c['id'], "n": c['name'], "l": c['logo'], "p": []} for c in src['channels']}

        for p in src['programs']:
            if p['cid'] in chan_map and len(chan_map[p['cid']]['p']) < 15:
                chan_map[p['cid']]['p'].append({"t": p['t'], "s": p['s'], "e": p['e'], "d": p['d']})

        for cdata in chan_map.values():
            search_db.append({
                "id": cdata['id'],
                "n": cdata['n'],
                "l": cdata['l'],
                "c": src['name'],
                "f": filename,
                "p": cdata['p'][:3]
            })
            if cdata['p']:
                cdata['p'].sort(key=lambda x: x['s'])
                country_db.append(cdata)

        if country_db:
            country_db.sort(key=lambda x: x['n'].lower())
            with open(os.path.join(DATA_DIR, filename), "w", encoding="utf-8") as f:
                json.dump(country_db, f, separators=(',', ':'), ensure_ascii=False)
            final_countries.append({
                "name": src['name'],
                "slug": country_slug,
                "file": filename,
                "count": len(country_db),
                "updated": src['age'],
                "external": src.get('is_external', False)
            })

    final_countries.sort(key=lambda x: x['name'].lower())
    with open(os.path.join(DATA_DIR, "countries.json"), "w", encoding="utf-8") as f:
        json.dump(final_countries, f, indent=2, ensure_ascii=False)

    search_db.sort(key=lambda x: x['n'].lower())
    with open(os.path.join(DATA_DIR, "search_db.json"), "w", encoding="utf-8") as f:
        json.dump(search_db, f, separators=(',', ':'), ensure_ascii=False)

    # 5. XMLTV Global para la APP
    print("📺 Generando guide.xml global...")
    XML_OUTPUT = os.path.join(EPG_DIR, "guide.xml")
    GZ_OUTPUT = os.path.join(EPG_DIR, "guide.xml.gz")
    def clean(t): return t.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;')
    with open(XML_OUTPUT, 'w', encoding='utf-8') as x:
        x.write('<?xml version="1.0" encoding="UTF-8"?>\n<tv generator-info-name="NovaEPG">\n')
        for src in sources:
            for c in src['channels']:
                x.write(f'  <channel id="{c["id"]}"><display-name>{clean(c["name"])}</display-name>')
                if c["logo"]: x.write(f'<icon src="{clean(c["logo"])}" />')
                x.write('</channel>\n')
        for src in sources:
            for p in src['programs']:
                x.write(f'  <programme start="{p["s"]} +0000" stop="{p["e"]} +0000" channel="{p["cid"]}"><title lang="es">{clean(p["t"])}</title>')
                if p["d"]: x.write(f'<desc lang="es">{clean(p["d"])}</desc>')
                x.write('</programme>\n')
        x.write('</tv>')
    with open(XML_OUTPUT, 'rb') as f_in, gzip.open(GZ_OUTPUT, 'wb') as f_out: f_out.writelines(f_in)
    try: os.remove(XML_OUTPUT)
    except: pass
    print("✅ Proceso terminado con éxito.")

if __name__ == "__main__":
    run()
