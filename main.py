from fastapi import FastAPI, UploadFile, File, Query
import tempfile
import ifcopenshell

# util helpers (come with ifcopenshell)
from ifcopenshell.util.element import get_psets, get_type
from ifcopenshell.util.placement import get_local_placement

app = FastAPI()


@app.get("/")
def root():
    return {"status": "IFC LAB RUNNING", "endpoints": ["/analyze", "/elements", "/psets", "/quantities"]}


def _open_ifc_from_upload(file: UploadFile) -> ifcopenshell.file:
    suffix = ".ifc"
    if file.filename and "." in file.filename:
        suffix = "." + file.filename.split(".")[-1].lower()

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(file.file.read())
        path = tmp.name

    return ifcopenshell.open(path)


def _iter_products(model: ifcopenshell.file):
    # IfcProduct covers building elements & more; safe default
    for el in model.by_type("IfcProduct"):
        yield el


def _basic_el_dict(el):
    return {
        "guid": getattr(el, "GlobalId", None),
        "type": el.is_a(),
        "name": getattr(el, "Name", None),
    }


@app.post("/analyze")
async def analyze(
    file: UploadFile = File(...),
    preview: int = Query(200, ge=0, le=2000),
):
    """
    Fast summary: element type counts + optional preview list.
    """
    model = _open_ifc_from_upload(file)

    counts = {}
    preview_list = []
    total = 0

    for el in _iter_products(model):
        t = el.is_a()
        counts[t] = counts.get(t, 0) + 1
        total += 1
        if preview and len(preview_list) < preview:
            preview_list.append(_basic_el_dict(el))

    return {
        "filename": file.filename,
        "elements_total": total,
        "types": counts,
        "preview": preview_list,
    }


@app.post("/elements")
async def elements(
    file: UploadFile = File(...),
    limit: int = Query(500, ge=1, le=5000),
):
    """
    Returns a list of elements (guid/type/name + type-object info if available).
    """
    model = _open_ifc_from_upload(file)

    out = []
    for el in _iter_products(model):
        d = _basic_el_dict(el)

        # Add type info if available (e.g. IfcWallType)
        try:
            t = get_type(el)
            if t:
                d["type_object"] = {
                    "type": t.is_a(),
                    "name": getattr(t, "Name", None),
                    "guid": getattr(t, "GlobalId", None),
                }
        except Exception:
            pass

        out.append(d)
        if len(out) >= limit:
            break

    return {"limit": limit, "items": out}


@app.post("/psets")
async def psets(
    file: UploadFile = File(...),
    limit: int = Query(200, ge=1, le=1000),
    pset_limit_per_element: int = Query(30, ge=1, le=200),
):
    """
    Returns PropertySets (Psets) for first N elements.
    """
    model = _open_ifc_from_upload(file)

    items = []
    for el in _iter_products(model):
        d = _basic_el_dict(el)
        try:
            p = get_psets(el)  # dict of psets -> properties
            # keep response small
            if isinstance(p, dict):
                # limit number of psets
                trimmed = dict(list(p.items())[:pset_limit_per_element])
                d["psets"] = trimmed
            else:
                d["psets"] = {}
        except Exception:
            d["psets"] = {}

        items.append(d)
        if len(items) >= limit:
            break

    return {"limit": limit, "items": items}


@app.post("/quantities")
async def quantities(
    file: UploadFile = File(...),
    limit: int = Query(200, ge=1, le=1000),
):
    """
    Tries to extract quantities from Psets that often contain QTO (Quantity Takeoff).
    Many IFCs store quantities in Psets like 'Qto_WallBaseQuantities' etc.
    """
    model = _open_ifc_from_upload(file)

    items = []
    for el in _iter_products(model):
        d = _basic_el_dict(el)
        qto = {}
        try:
            p = get_psets(el)
            if isinstance(p, dict):
                # common pattern: psets starting with "Qto_"
                for k, v in p.items():
                    if isinstance(k, str) and k.startswith("Qto_") and isinstance(v, dict):
                        qto[k] = v
        except Exception:
            pass

        d["quantities"] = qto
        items.append(d)

        if len(items) >= limit:
            break

    return {"limit": limit, "items": items}
