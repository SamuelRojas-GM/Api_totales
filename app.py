import asyncio
import logging
import sys
import traceback
import time  # Para medir latencia
from typing import Optional, Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException as FastHTTPException
from pydantic import BaseModel, Field, constr


# ==========================================
# 🎨 CONFIGURACIÓN DE LOGS (CON COLORES)
# ==========================================
# Definimos códigos ANSI para Cloud Run
class CloudRunFormatter(logging.Formatter):
    # Colores
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    RED = "\033[91m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    FORMAT = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"

    LEVEL_COLORS = {
        logging.DEBUG: CYAN,
        logging.INFO: GREEN,
        logging.WARNING: YELLOW,
        logging.ERROR: RED,
        logging.CRITICAL: RED + BOLD,
    }

    def format(self, record):
        color = self.LEVEL_COLORS.get(record.levelno, self.RESET)
        log_fmt = f"{color}{self.FORMAT}{self.RESET}"
        formatter = logging.Formatter(log_fmt, datefmt="%Y-%m-%d %H:%M:%S")
        return formatter.format(record)


# Configuración global
logger = logging.getLogger("api")
logger.setLevel(logging.DEBUG)

# Handler de consola (Cloud Run captura stdout)
console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(CloudRunFormatter())
logger.addHandler(console_handler)

# Nota: FileHandler suele dar problemas en Cloud Run (filesystem read-only)
# Solo usarlo si tienes montado un volumen o usas /tmp/

# ==========================================
# IMPORTS Y HELPERS (Sin cambios)
# ==========================================
from Source.consulta_Runt import ConsultaRunt
from Source.Variables import Consulta_prenda, Consulta_propietarios, limitaciones_propiedad, validar_propietario


def _keys(d: Any):
    return sorted(list(d.keys())) if isinstance(d, dict) else str(type(d).__name__)


def where(exc: Exception | None = None):
    tb = exc.__traceback__ if exc and exc.__traceback__ else sys.exc_info()[2]
    if not tb: return ("<unknown>", -1, "<unknown>")
    while tb.tb_next: tb = tb.tb_next
    code = tb.tb_frame.f_code
    return (code.co_filename, tb.tb_lineno, code.co_name)


# ==========================================
# SCHEMAS
# =========================
PlacaStr = constr(pattern=r"^[A-Za-z0-9]{5,8}$")


class ConsultaInput(BaseModel):
    placa: PlacaStr
    numero_documento: Optional[str] = None
    nombre_propietario: Optional[str] = None


class ConsultaResponse(BaseModel):
    placa: str
    limitaciones_propiedad: bool
    prenda: bool
    total_propietarios: int
    propietario_valido: Optional[bool] = None
    organismoTransito: str


# ==========================================
# FASTAPI APP + MIDDLEWARE DE LOGS
# ==========================================
app = FastAPI(title="Consultas Vehiculares API")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """
    Este middleware asegura que veas CADA petición que entra
    y CADA respuesta que sale, incluso si hay error 500.
    """
    start_time = time.time()
    path = request.url.path
    method = request.method

    # Log de entrada (Azul/Cyan)
    logger.info(f"🚀 INCOMING: {method} {path}")

    try:
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000

        # Log de salida exitosa (Verde)
        logger.info(f"✅ FINISHED: {method} {path} - Status: {response.status_code} - Time: {process_time:.2f}ms")
        return response
    except Exception as e:
        # Log de salida con error (Rojo)
        logger.error(f"🧨 CRASHED: {method} {path} - Error: {str(e)}")
        raise e


# ---------- Handlers de errores ----------
@app.exception_handler(FastHTTPException)
async def http_exception_logger(request: Request, exc: FastHTTPException):
    f, ln, fn = where(exc)
    logger.warning(f"⚠️ HTTP {exc.status_code} en {fn}(): {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "file": f, "line": ln, "function": fn},
    )


# ---------- Endpoints ----------
@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/consulta", response_model=ConsultaResponse)
async def consultar_vehiculo(payload: ConsultaInput):
    placa = payload.placa.strip().upper()

    # 1) Consulta RUNT
    logger.debug(f"🔍 Iniciando ConsultaRunt para: {placa}")
    try:
        # Importante: to_thread es bueno para librerías síncronas (requests/selenium)
        runt_json = await asyncio.to_thread(ConsultaRunt, placa)
        logger.debug(f"📥 RUNT obtenido exitosamente para {placa}")
    except Exception as e:
        f, ln, fn = where(e)
        logger.error(f"❌ Fallo en ConsultaRunt: {str(e)}")
        raise HTTPException(status_code=502, detail="Error en servicio RUNT externo")

    # 2) Post-proceso
    try:
        limitaciones = bool(limitaciones_propiedad(runt_json))
        prenda = bool(Consulta_prenda(runt_json))
        n_prop = int(Consulta_propietarios(runt_json))

        propietario_valido = None
        organismo_Transito = runt_json.get("organismoTransito")
        if payload.numero_documento and payload.nombre_propietario:
            propietario_valido = bool(
                validar_propietario(
                    runt_json,
                    numero_documento=payload.numero_documento,
                    nombre=payload.nombre_propietario,
                )
            )

        logger.info(f"✨ Proceso completado para placa {placa}")
        return ConsultaResponse(
            placa=placa,
            limitaciones_propiedad=limitaciones,
            prenda=prenda,
            total_propietarios=n_prop,
            propietario_valido=propietario_valido,
            organismoTransito=organismo_Transito
        )

    except Exception as e:
        logger.error(f"❌ Error en lógica de negocio: {str(e)}")
        raise HTTPException(status_code=500, detail="Error procesando datos de RUNT")