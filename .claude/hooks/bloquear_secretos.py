"""Hook PreToolUse: bloquea `git add` / `git commit` si van a quedar en stage
un *.xlsx o un *.json con "private_key". Sale con código 2 para bloquear."""
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path


def git(*args):
    r = subprocess.run(['git', *args], capture_output=True, text=True, encoding='utf-8', errors='replace',
                       check=False)
    return r.stdout


def raiz_repo():
    return Path(git('rev-parse', '--show-toplevel').strip() or '.')


def peligroso(ruta):
    p = Path(ruta.strip().strip('"'))
    if not p.is_absolute() and not p.exists():
        p = raiz_repo() / p          # git devuelve rutas relativas a la raíz del repo
    sufijo = p.suffix.lower()
    if sufijo == '.xlsx':
        return 'archivo Excel con datos personales'
    if p.name == 'secrets.toml':
        return 'secrets de Streamlit'
    if p.name.startswith('profeapp2-') and sufijo == '.json':
        return 'clave de cuenta de servicio'
    if sufijo in ('.json', '.toml', '.txt', '.env', '.cfg', '.ini', '.yaml', '.yml'):
        try:
            contenido = p.read_text(encoding='utf-8', errors='ignore')
        except OSError:
            return None
        if 'private_key' in contenido or 'app_password' in contenido.replace('.get("app_password")', ''):
            return 'archivo con private_key / app_password'
    return None


def segmentos_git(comando, sub):
    """Devuelve los argumentos de cada `git <sub> ...` dentro de un comando compuesto."""
    for parte in re.split(r'&&|\|\||;|\||\n', comando):
        try:
            tokens = shlex.split(parte, posix=True)
        except ValueError:
            tokens = parte.split()
        if 'git' not in tokens:
            continue
        resto = tokens[tokens.index('git') + 1:]
        while resto and resto[0].startswith('-'):        # git -C dir / -c k=v
            resto = resto[2:] if resto[0] in ('-C', '-c') else resto[1:]
        if resto and resto[0] == sub:
            yield resto[1:]


def main():
    crudo = sys.stdin.read()
    try:
        datos = json.loads(crudo)
    except Exception:
        # Falla cerrado si no se puede leer la entrada y parece un add/commit
        return 2 if re.search(r'\bgit\b.*\b(add|commit)\b', crudo) else 0
    comando = (datos.get('tool_input') or {}).get('command', '') or ''
    if 'git' not in comando:
        return 0
    try:
        return revisar(comando)
    except Exception as e:  # falla cerrado: ante la duda, no se commitea
        if re.search(r'\bgit\b.*\b(add|commit)\b', comando):
            print(f"BLOQUEADO: el hook de secretos falló ({e}); revisá el stage a mano.", file=sys.stderr)
            return 2
        return 0


def revisar(comando):
    candidatos = set()
    for args in segmentos_git(comando, 'add'):
        salida = git('add', '--dry-run', *args)
        candidatos.update(re.findall(r"^add '(.+)'$", salida, flags=re.M))
        candidatos.update(a for a in args if not a.startswith('-'))
    for args in segmentos_git(comando, 'commit'):
        candidatos.update(git('diff', '--cached', '--name-only').splitlines())
        candidatos.update(a for a in args if not a.startswith('-') and Path(a).exists())
        if any(a in ('-a', '--all') or (a.startswith('-') and not a.startswith('--') and 'a' in a[1:])
               for a in args if a not in ('-m',)):
            candidatos.update(git('diff', '--name-only').splitlines())

    problemas = [(c, m) for c in candidatos if (m := peligroso(c))]
    if problemas:
        detalle = '\n'.join(f"  - {c}: {m}" for c, m in sorted(problemas))
        print("BLOQUEADO por .claude/hooks/bloquear_secretos.py: no se pueden commitear secretos ni "
              f"Excel.\n{detalle}\nSacalos del stage con `git restore --staged <archivo>`.", file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
