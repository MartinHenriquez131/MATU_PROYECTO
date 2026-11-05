#!/usr/bin/env bash
# e2e del relevo contra staging por HTTPS (MATU-25, definición de terminado, ítem 3). Solo datos
# sintéticos: usa la cuenta carmen@example.com de infra/semillas/demo.py.
#
# Hace, como lo haría la familia y luego el relevo:
#   1. entra como Carmen y busca su grupo y a María;
#   2. escribe los tres campos de la ficha si están vacíos (textos inventados);
#   3. comparte un acceso de relevo con un teléfono inventado y lo abre: presentación, canje con el
#      PIN y lectura de la ficha, con la cookie de relevo;
#   4. corta ese acceso y comprueba que ya no abre;
#   5. comparte un segundo acceso para abrirlo en el teléfono, e imprime su enlace y su PIN.
#
# Al final imprime el token y el PIN del primer acceso, ya cortado, para hacer el grep de los logs.
# La contraseña de la semilla se pide sin mostrarla y no se guarda en ningún archivo.
#
# Uso, desde la raíz del repositorio (Git Bash, macOS o Linux; necesita curl y python):
#   bash infra/railway/e2e_relevo.sh https://matu-api-production.up.railway.app
set -euo pipefail

BASE="${1:?Uso: bash infra/railway/e2e_relevo.sh https://<dominio>}"
BASE="${BASE%/}"
EMAIL="carmen@example.com"
# En Windows, "python3" puede ser el acceso directo de la Microsoft Store, que no ejecuta nada: se prueba
# cada candidato antes de usarlo
PY=""
for candidato in python3 python py; do
  if command -v "$candidato" >/dev/null 2>&1 && "$candidato" -c "import json" >/dev/null 2>&1; then
    PY="$candidato"; break
  fi
done
[ -n "$PY" ] || { echo "FALLA: no se encontró Python (python3, python o py)" >&2; exit 1; }
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
COOKIES="$TMP/cookies"

# tr quita el \r que agrega Python en Windows: un id con \r rompe la cabecera X-Grupo-Id (400)
json() { "$PY" -c "import json,sys; d=json.load(sys.stdin); print($1)" | tr -d '\r'; }
falla() { echo "FALLA: $*" >&2; exit 1; }

printf 'Contraseña de la semilla (no se ve al escribir): '
read -rs CONTRASENA
echo

# 1 · Sesión de Carmen
CUERPO="$("$PY" -c 'import json,sys; print(json.dumps({"email":sys.argv[1],"contrasena":sys.argv[2]}))' "$EMAIL" "$CONTRASENA" | tr -d '\r')"
unset CONTRASENA
R="$(curl -sS -w '\n%{http_code}' -X POST "$BASE/v1/sesiones" -H 'Content-Type: application/json' -d "$CUERPO")"
[ "$(tail -n1 <<<"$R")" = 200 ] || falla "entrar como $EMAIL: $(tail -n1 <<<"$R")"
TOKEN_SESION="$(head -n -1 <<<"$R" | json 'd["access_token"]')"
AUT=(-H "Authorization: Bearer $TOKEN_SESION")
echo "1. Sesión de Carmen: 200"

GRUPO="$(curl -sS "${AUT[@]}" "$BASE/v1/grupos" | json 'd[0]["id"]')"
PERSONA="$(curl -sS "${AUT[@]}" -H "X-Grupo-Id: $GRUPO" "$BASE/v1/grupos/$GRUPO/personas-cuidadas" | json 'd[0]["id"]')"
CAB=("${AUT[@]}" -H "X-Grupo-Id: $GRUPO" -H 'Content-Type: application/json')
echo "   Grupo y persona encontrados"

# 2 · Ficha: escribe cada campo solo si nunca se escribió (If-None-Match: *; 412 = ya tenía texto)
escribir() {
  local codigo cuerpo
  # El cuerpo lo arma Python con escapes \uXXXX: en Git Bash las tildes salen en la página de códigos de
  # Windows y la API rechaza el JSON con 400
  cuerpo="$("$PY" -c 'import json,sys; print(json.dumps({"texto": sys.argv[1]}))' "$2" | tr -d '\r')"
  codigo="$(curl -sS -o /dev/null -w '%{http_code}' -X PUT "${CAB[@]}" -H 'If-None-Match: *' \
    "$BASE/v1/personas-cuidadas/$PERSONA/plan/ficha/$1" -d "$cuerpo")"
  case "$codigo" in 200|201|412) echo "2. Campo $1: $codigo" ;; *) falla "escribir $1: $codigo" ;; esac
}
escribir rutina "Desayuna a las 8 con pan tostado. Camina 15 minutos después de almuerzo. Siesta de 15 a 16."
escribir manejo_situaciones "Si se inquieta en la tarde, poner su radio y conversar de su pueblo. No discutir."
escribir red_apoyo "Carmen, su hija, de 8 a 20. Si no contesta, Rodrigo, su hijo."

compartir() {
  local motivo="$1"
  curl -sS -w '\n%{http_code}' -X POST "${CAB[@]}" "$BASE/v1/personas-cuidadas/$PERSONA/plan/accesos-relevo" \
    -d "{\"nombre_relevo\": \"Rosa\", \"telefono_relevo\": \"+56900000000\", \"campos\": [\"rutina\", \"manejo_situaciones\", \"red_apoyo\"], \"motivo\": \"$motivo\", \"relevo_informado\": true}"
}

# 3 · Primer acceso: se abre aquí mismo, como lo haría la página /r
R="$(compartir turno_de_noche)"
[ "$(tail -n1 <<<"$R")" = 201 ] || falla "compartir: $(tail -n1 <<<"$R") $(head -n -1 <<<"$R")"
ACCESO="$(head -n -1 <<<"$R" | json 'd["id"]')"
URL="$(head -n -1 <<<"$R" | json 'd["url"]')"
PIN="$(head -n -1 <<<"$R" | json 'd["pin"]')"
TOKEN_RELEVO="${URL##*#}"
echo "3. Acceso compartido: 201"

C="$(curl -sS -o /dev/null -w '%{http_code}' -X POST "$BASE/v1/relevo/presentacion" -H 'Content-Type: application/json' -d "{\"token\": \"$TOKEN_RELEVO\"}")"
[ "$C" = 200 ] || falla "presentación: $C"; echo "   Presentación: $C"
C="$(curl -sS -o /dev/null -w '%{http_code}' -c "$COOKIES" -X POST "$BASE/v1/relevo/canje" -H 'Content-Type: application/json' -d "{\"token\": \"$TOKEN_RELEVO\", \"pin\": \"$PIN\"}")"
[ "$C" = 204 ] || falla "canje con el PIN: $C"; echo "   Canje con el PIN: $C"
R="$(curl -sS -w '\n%{http_code}' -b "$COOKIES" "$BASE/v1/relevo/ficha")"
[ "$(tail -n1 <<<"$R")" = 200 ] || falla "leer la ficha como relevo: $(tail -n1 <<<"$R")"
grep -q "pan tostado\|Desayuna" <<<"$R" || echo "   (la ficha ya tenía otro texto: se leyó igual)"
echo "   Ficha leída como relevo: 200"

# 4 · Cortar el acceso: la sesión de relevo deja de leer
C="$(curl -sS -o /dev/null -w '%{http_code}' -X DELETE "${AUT[@]}" -H "X-Grupo-Id: $GRUPO" "$BASE/v1/accesos-relevo/$ACCESO")"
[ "$C" = 204 ] || falla "cortar el acceso: $C"; echo "4. Acceso cortado: $C"
C="$(curl -sS -o /dev/null -w '%{http_code}' -b "$COOKIES" "$BASE/v1/relevo/ficha")"
case "$C" in 401|404|410) echo "   La ficha ya no abre: $C" ;; *) falla "después de cortar, la ficha respondió $C" ;; esac

# 5 · Segundo acceso, para el teléfono
R="$(compartir fin_de_semana_fuera)"
[ "$(tail -n1 <<<"$R")" = 201 ] || falla "compartir para el teléfono: $(tail -n1 <<<"$R")"
echo "5. Acceso para el teléfono: 201"
echo
echo "== Abre esto en el teléfono (vence en 24 horas) =="
echo "   Enlace: $(head -n -1 <<<"$R" | json 'd["url"]')"
echo "   PIN:    $(head -n -1 <<<"$R" | json 'd["pin"]')"
echo
echo "== Para el grep de los logs (acceso ya cortado, no abre) =="
echo "   token: $TOKEN_RELEVO"
echo "   PIN:   $PIN"
echo
echo "e2e del relevo por HTTPS: OK"
