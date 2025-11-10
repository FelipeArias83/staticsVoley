# PMV - Registro de Acciones (Saque / Ataque / Recepción)

App mínima para registrar acciones de jugadores y ver estadísticas instantáneas. Usa Streamlit para UI y SQLite para persistencia.

Cómo ejecutar (PowerShell / Windows):

```powershell
# instalar dependencias en el virtualenv (si no están instaladas)
C:/proyectos/Udemy/Voley/PMV/.venv/Scripts/python.exe -m pip install -r requirements.txt

# ejecutar la app Streamlit
C:/proyectos/Udemy/Voley/PMV/.venv/Scripts/python.exe -m streamlit run streamlit_app.py
```

Notas:
- La DB por defecto es `pmv.db` en la carpeta del proyecto. Puedes cambiarla poniendo la variable de entorno `DB_PATH`.
- Acciones soportadas: `serve_point`, `serve_error`, `attack_point`, `attack_error`, `reception_good`, `reception_bad`.
