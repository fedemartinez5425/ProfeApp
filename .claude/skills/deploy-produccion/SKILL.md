---
name: deploy-produccion
description: Checklist obligatorio antes de pushear a main en ProfeApp (push a main = deploy a producción en Streamlit Cloud). Usalo cada vez que vayas a hacer git push.
---

# Deploy a producción (push a `main`)

Push a `main` = deploy inmediato en Streamlit Community Cloud. No se pushea nada que no pase todo esto.
Si un paso falla, se arregla y se vuelve a empezar desde el paso 1.

1. **Tests**: `.venv\Scripts\python -m pytest -q` → todo en verde.
2. **Compilación**: `.venv\Scripts\python -m py_compile app.py sheets.py logica.py`.
3. **Smoke test** (app levantada de verdad):
   ```bash
   .venv/Scripts/python -m streamlit run app.py --server.headless true --server.port 8501   # en segundo plano
   curl -s -o /dev/null -w "%{http_code}" http://localhost:8501/            # 200
   curl -s http://localhost:8501/_stcore/health                             # ok
   ```
   Después cortá el proceso de Streamlit.
4. **Secretos**: `git status` y `git diff --cached --name-only` sin `*.json` (salvo `.claude/settings.json`),
   sin `*.xlsx` y sin `.streamlit/secrets.toml`. El hook `.claude/hooks/bloquear_secretos.py` lo refuerza.
5. **Revisión**: correr el subagente `revisor-codigo` sobre el diff contra `origin/main`. Cero hallazgos
   BLOQUEANTE o ALTA sin resolver.
6. **Commit** en español, chico y descriptivo; **push** a `origin main`.
7. **Avisar al usuario** qué paso manual hace falta (secrets nuevos en Streamlit Cloud → Settings → Secrets,
   importar hojas, columnas nuevas) y anotarlo en `CHANGELOG.md`.
