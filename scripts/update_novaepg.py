import os
from datetime import datetime, timedelta

def process_channel(channel_dir):
    template_path = os.path.join(channel_dir, f"{os.path.basename(channel_dir)}.template.xml")
    output_path = os.path.join(channel_dir, f"{os.path.basename(channel_dir)}.xml")

    if not os.path.exists(template_path):
        print(f"   ⚠️ No se encontró plantilla en {channel_dir}")
        return

    # 1. Calcular el "Hoy" en Paraguay (UTC-3)
    now_py = datetime.utcnow() - timedelta(hours=3)

    # 2. Encontrar el lunes de la semana actual
    monday_py = now_py - timedelta(days=now_py.weekday())

    # 3. Preparar los reemplazos
    days_tags = {
        "{{LUNES}}": (monday_py + timedelta(days=0)).strftime('%Y%m%d'),
        "{{MARTES}}": (monday_py + timedelta(days=1)).strftime('%Y%m%d'),
        "{{MIERCOLES}}": (monday_py + timedelta(days=2)).strftime('%Y%m%d'),
        "{{JUEVES}}": (monday_py + timedelta(days=3)).strftime('%Y%m%d'),
        "{{VIERNES}}": (monday_py + timedelta(days=4)).strftime('%Y%m%d'),
        "{{SABADO}}": (monday_py + timedelta(days=5)).strftime('%Y%m%d'),
        "{{DOMINGO}}": (monday_py + timedelta(days=6)).strftime('%Y%m%d')
    }

    print(f"   📅 Procesando {os.path.basename(channel_dir)} para la semana del {monday_py.strftime('%Y-%m-%d')}")

    with open(template_path, 'r', encoding='utf-8') as f:
        content = f.read()

    new_content = content
    for tag, date_str in days_tags.items():
        new_content = new_content.replace(tag, date_str)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"   ✅ Canal {os.path.basename(channel_dir)} actualizado.")

def main():
    print("🚀 Iniciando Actualización Masiva de NovaEPG...")

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    novaepg_dir = os.path.join(base_dir, 'novaepg')

    if not os.path.exists(novaepg_dir):
        print("❌ Error: Directorio novaepg no encontrado.")
        return

    for folder in os.listdir(novaepg_dir):
        full_path = os.path.join(novaepg_dir, folder)
        if os.path.isdir(full_path):
            process_channel(full_path)

    print("🏁 Fin de la actualización masiva.")

if __name__ == "__main__":
    main()
