import os
from datetime import datetime, timedelta

def generate():
    path = os.path.join(os.path.dirname(__file__), "novasports.xml")
    now = datetime.now()
    # Generamos para 7 días, bloques de 4 horas
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<tv>\n'
    xml += '  <channel id="NovaSports">\n'
    xml += '    <display-name>NOVASPORTS</display-name>\n'
    xml += '    <icon src="https://raw.githubusercontent.com/novaplaytv/novaimg/main/novasplash.webp" />\n'
    xml += '  </channel>\n'

    start_date = now - timedelta(days=1)
    for i in range(42): # 7 días * 6 bloques de 4h
        s = start_date + timedelta(hours=i*4)
        e = s + timedelta(hours=4)
        s_str = s.strftime("%Y%m%d%H%M%S") + " +0000"
        e_str = e.strftime("%Y%m%d%H%M%S") + " +0000"

        xml += f'  <programme start="{s_str}" stop="{e_str}" channel="NovaSports">\n'
        xml += '    <title lang="es">EVENTOS NOVASPORTS</title>\n'
        xml += '    <desc lang="es">Toda la mejor programación deportiva 24/7 en NOVAPLAY. Fútbol, Basket, Tenis y más.</desc>\n'
        xml += '  </programme>\n'

    xml += '</tv>'

    with open(path, "w", encoding="utf-8") as f:
        f.write(xml)
    print(f"✅ Generado: {path}")

if __name__ == "__main__":
    generate()
