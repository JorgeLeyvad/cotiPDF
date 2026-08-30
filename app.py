import os
import io
import json
import base64
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from jinja2 import Environment, FileSystemLoader
from playwright.sync_api import sync_playwright

app = FastAPI(title="Gestor de Cotizaciones, Contratos y Briefs PDF")

STORAGE_DIR = os.path.join("storage", "pdfs")
DATA_DIR = os.path.join("storage", "data")
STATIC_DIR = "static"

os.makedirs(STORAGE_DIR, exist_ok=True)
os.makedirs(DATA_DIR, exist_ok=True)

env = Environment(loader=FileSystemLoader("templates"))

def get_logo_data_uri():
    logo_path = os.path.join(STATIC_DIR, "logo.png")
    if os.path.exists(logo_path):
        with open(logo_path, "rb") as image_file:
            encoded = base64.b64encode(image_file.read()).decode("utf-8")
            return f"data:image/png;base64,{encoded}"
    return None

def generar_pdf_playwright(html_content: str, output_path: Optional[str] = None) -> bytes:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.set_content(html_content, wait_until="networkidle")
        pdf_bytes = page.pdf(
            path=output_path,
            format="A4",
            print_background=True,
            margin={"top": "10mm", "bottom": "10mm", "left": "12mm", "right": "12mm"}
        )
        browser.close()
    return pdf_bytes

# --- Modelos de Datos ---
class ItemAlcance(BaseModel):
    modulo: str
    descripcion: str
    tipo: Optional[str] = "NUEVO"

class ConceptoCosto(BaseModel):
    concepto: str
    descripcion: str = ""
    precio: float

class FasePago(BaseModel):
    nombre: str
    descripcion: str
    monto: float
    fecha_entrega: Optional[str] = ""
    fecha_pago: Optional[str] = ""

class SeccionPreguntas(BaseModel):
    titulo: str
    preguntas: List[str]

class CheckboxSeccion(BaseModel):
    nombre: str
    marcado: bool = False

class DocumentoSchema(BaseModel):
    tipo_documento: str = "COTIZACION"  # "COTIZACION", "CONTRATO" o "BRIEF"
    folio: str
    empresa: str = "Elevate Web Solutions"
    subtitulo_doc: str = "Propuesta de Desarrollo Web & Renovación"
    fecha: str
    validez: str = "15 días naturales"
    cliente: str
    responsable: Optional[str] = ""
    proyecto: str
    marca: str
    modalidad: str = "Esquema Ágil por Entregas"
    resumen: str = "Modernización integral visual, técnica y funcional de la landing page."
    total: float = 0.0
    items_alcance: List[ItemAlcance] = []
    desglose_costos: List[ConceptoCosto] = []
    fases: List[FasePago] = []
    terminos: List[str] = []
    # Campos específicos para el Brief
    introduccion_brief: Optional[str] = "Para entender a fondo las necesidades del proyecto y preparar una propuesta técnica y de diseño adecuada, le agradeceremos responder el siguiente cuestionario."
    secciones_preguntas: List[SeccionPreguntas] = []
    checkboxes_secciones: List[CheckboxSeccion] = []

# --- Rutas ---
@app.get("/", response_class=HTMLResponse)
def home():
    template = env.get_template("index.html")
    return template.render()

@app.post("/preview/")
def preview_documento(data: DocumentoSchema):
    if data.tipo_documento == "BRIEF":
        template_name = "brief_template.html"
    elif data.tipo_documento == "CONTRATO":
        template_name = "contrato_template.html"
    else:
        template_name = "cotizacion_template.html"

    template = env.get_template(template_name)
    context = data.model_dump()
    context["logo_base64"] = get_logo_data_uri()
    
    html_rendered = template.render(context)
    pdf_bytes = generar_pdf_playwright(html_rendered)
    
    return StreamingResponse(
        io.BytesIO(pdf_bytes),
        media_type="application/pdf",
        headers={"Content-Disposition": "inline; filename=preview.pdf"}
    )

@app.post("/documentos/", status_code=201)
def save_documento(data: DocumentoSchema):
    prefix = data.tipo_documento
    file_id = f"{prefix}_{data.folio}"
    
    pdf_path = os.path.join(STORAGE_DIR, f"{file_id}.pdf")
    json_path = os.path.join(DATA_DIR, f"{file_id}.json")
    
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(data.model_dump(), f, ensure_ascii=False, indent=2)
        
    if data.tipo_documento == "BRIEF":
        template_name = "brief_template.html"
    elif data.tipo_documento == "CONTRATO":
        template_name = "contrato_template.html"
    else:
        template_name = "cotizacion_template.html"

    template = env.get_template(template_name)
    context = data.model_dump()
    context["logo_base64"] = get_logo_data_uri()
    
    html_rendered = template.render(context)
    generar_pdf_playwright(html_rendered, output_path=pdf_path)
    
    return {"message": "Documento generado exitosamente", "file_id": file_id}

@app.get("/documentos/{file_id}")
def get_pdf(file_id: str):
    pdf_path = os.path.join(STORAGE_DIR, f"{file_id}.pdf")
    if not os.path.exists(pdf_path):
        raise HTTPException(status_code=404, detail="Archivo PDF no encontrado")
    return FileResponse(pdf_path, media_type="application/pdf", filename=f"{file_id}.pdf")

@app.get("/api/data/{file_id}")
def get_document_data(file_id: str):
    json_path = os.path.join(DATA_DIR, f"{file_id}.json")
    if not os.path.exists(json_path):
        raise HTTPException(status_code=404, detail="Datos no encontrados")
    with open(json_path, "r", encoding="utf-8") as f:
        return json.load(f)

@app.get("/api/documentos")
def list_documentos():
    files = [f.replace(".json", "") for f in os.listdir(DATA_DIR) if f.endswith(".json")]
    return {"documentos": sorted(files, reverse=True)}

@app.delete("/documentos/{file_id}")
def delete_documento(file_id: str):
    pdf_path = os.path.join(STORAGE_DIR, f"{file_id}.pdf")
    json_path = os.path.join(DATA_DIR, f"{file_id}.json")
    if os.path.exists(pdf_path): os.remove(pdf_path)
    if os.path.exists(json_path): os.remove(json_path)
    return {"message": "Eliminado"}