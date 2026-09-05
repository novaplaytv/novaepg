import json
import os
import re
from datetime import datetime, timezone

def parse_xmltv_date(date_str):
    if not date_str: return ""
    try:
        # Extraer fecha y offset: 20260904073000 -0300
        match = re.search(r'(\d{14})\s*([+-]\d{4})?', date_str)
        if match:
            date_part = match.group(1)
            offset_part = match.group(2)
            if offset_part:
                dt = datetime.strptime(date_part + offset_part, "%Y%m%d%H%M%S%z")
            else:
                dt = datetime.strptime(date_part, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc).strftime('%Y%m%d%H%M%S')
    except:
        pass
    return re.sub(r'[^0-9]', '', date_str)[:14]

def main():
    print("🚀 Generando Base de Datos EPG Resiliente (v103)...")

    current_dir = os.path.dirname(os.path.abspath(__file__))
    base_dir = os.path.dirname(current_dir)
    input_file = os.path.join(base_dir, 'epg', 'guide.xml')
    output_file = os.path.join(base_dir, 'epg-search', 'epg_db.json')

    if not os.path.exists(input_file):
        print(f"❌ Error: No se encuentra {input_file}")
        return

    channels_map = {}
    now_utc = datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')

    # Regex ultra-flexibles
    re_channel = re.compile(r'<channel[^>]+id="([^"]+)"')
    re_display_name = re.compile(r'<display-name[^>]*>(.*?)</display-name>')
    re_icon = re.compile(r'<icon[^>]+src="([^"]+)"')
    re_prog = re.compile(r'<programme[^>]+start="([^"]+)"[^>]+stop="([^"]+)"[^>]+channel="([^"]+)"')
    re_title = re.compile(r'<title[^>]*>(.*?)</title>')

    try:
        print("📖 Procesando guía...")
        with open(input_file, 'r', encoding='utf-8', errors='ignore') as f:
            for line in f:
                # Buscar canales
                c_match = re_channel.search(line)
                if c_match:
                    ch_id = c_match.group(1)
                    name_match = re_display_name.search(line)
                    icon_match = re_icon.search(line)

                    name = name_match.group(1) if name_match else ch_id
                    icon = icon_match.group(1) if icon_match else ""
                    country = "LATAM"
                    if '#' in ch_id: country = ch_id.split('#')[0].upper()
                    elif '.' in ch_id:
                        parts = ch_id.split('.')
                        if len(parts) > 1:
                            # Extraer country code (AR, PY, UY...)
                            code = parts[1][:2].upper()
                            if code in ["AR", "PY", "UY", "CL", "BR"]: country = code

                    channels_map[ch_id] = {
                        'id': ch_id, 'name': name, 'logo': icon, 'country': country,
                        'site': ch_id.split('@')[-1] if '@' in ch_id else "XMLTV",
                        'progs': []
                    }
                    continue

                # Buscar programas
                p_match = re_prog.search(line)
                if p_match:
                    start_utc = parse_xmltv_date(p_match.group(1))
                    stop_utc = parse_xmltv_date(p_match.group(2))
                    ch_id = p_match.group(3)

                    if ch_id in channels_map and stop_utc > now_utc:
                        title_match = re_title.search(line)
                        title = title_match.group(1) if title_match else "Sin título"
                        title = title.replace('&amp;', '&').replace('&quot;', '"').replace('&apos;', "'").replace('&lt;', '<').replace('&gt;', '>')

                        if len(channels_map[ch_id]['progs']) < 5:
                            channels_map[ch_id]['progs'].append([title, start_utc, stop_utc])

        # Convertir a lista y limpiar canales sin programas
        final_list = []
        for ch_id, data in channels_map.items():
            if data['progs']:
                data['progs'].sort(key=lambda x: x[1])
                final_list.append(data)

        # Ordenar por nombre
        final_list.sort(key=lambda x: x['name'])

        os.makedirs(os.path.dirname(output_file), exist_ok=True)
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_list, f, separators=(',', ':'), ensure_ascii=False)

        print(f"✓ Éxito: {len(final_list)} canales con programación indexados.")

    except Exception as e:
        print(f"❌ Error crítico: {e}")
        exit(1)

if __name__ == "__main__":
    main()
